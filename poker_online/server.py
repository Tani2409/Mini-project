import json
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pokerkit import Automation, NoLimitTexasHoldem

from database import init_db, record_hand_result, room_history


BASE_DIR = Path(__file__).parent
DEFAULT_ROOM_CODE = "POKER"
AUTOMATIONS = tuple(Automation)

app = FastAPI(title="POKER Online")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
init_db()


@dataclass
class Player:
    player_id: str
    name: str
    socket: WebSocket | None = None
    connected: bool = True


@dataclass
class Room:
    code: str
    players: list[Player] = field(default_factory=list)
    state: object | None = None
    dealt_hole_cards: list[list[str]] = field(default_factory=list)
    folded_seats: set[int] = field(default_factory=set)
    hand_number: int = 0
    message: str = "Dang cho nguoi choi"
    last_event: dict = field(default_factory=dict)
    result_recorded: bool = False

    def seat_of(self, player_id):
        return next((i for i, player in enumerate(self.players) if player.player_id == player_id), None)

    def host_id(self):
        connected = next((player for player in self.players if player.connected), None)
        return connected.player_id if connected else (self.players[0].player_id if self.players else None)

    def start_hand(self):
        if len(self.players) < 2:
            raise ValueError("Can it nhat 2 nguoi choi")
        if len(self.players) > 6:
            raise ValueError("Ban da du 6 nguoi")

        stacks = tuple(self.state.stacks) if self.state is not None and not self.state.status else (1000,) * len(self.players)
        if len(stacks) != len(self.players) or sum(stack > 0 for stack in stacks) < 2:
            stacks = (1000,) * len(self.players)

        self.state = NoLimitTexasHoldem.create_state(
            AUTOMATIONS, True, 0, (10, 20), 20, stacks, len(self.players)
        )
        self.hand_number += 1
        self.dealt_hole_cards = [cards_to_strings(cards) for cards in self.state.hole_cards]
        self.folded_seats = set()
        self.result_recorded = False
        self.message = f"Van #{self.hand_number} bat dau"
        self.last_event = {"kind": "deal", "hand": self.hand_number, "seats": len(self.players)}

    def act(self, seat, action, amount=None):
        if self.state is None or not self.state.status:
            raise ValueError("Van bai chua bat dau")
        if self.state.actor_index != seat:
            raise ValueError("Chua den luot cua ban")

        previous_board = board_strings(self.state)
        if action == "fold" and self.state.can_fold():
            self.state.fold()
            self.folded_seats.add(seat)
            self.message = f"{self.players[seat].name} da fold"
            self.last_event = {"kind": "fold", "seat": seat}
        elif action == "call" and self.state.can_check_or_call():
            operation = self.state.check_or_call()
            self.message = f"{self.players[seat].name} check/call {operation.amount}"
            self.last_event = {"kind": "call", "seat": seat, "amount": int(operation.amount)}
        elif action == "raise":
            amount = int(amount or 0)
            if not self.state.can_complete_bet_or_raise_to(amount):
                raise ValueError("Muc raise khong hop le")
            self.state.complete_bet_or_raise_to(amount)
            self.message = f"{self.players[seat].name} raise toi {amount}"
            self.last_event = {"kind": "raise", "seat": seat, "amount": amount}
        else:
            raise ValueError("Hanh dong khong hop le")

        current_board = board_strings(self.state)
        if len(current_board) > len(previous_board):
            self.last_event = {
                **self.last_event,
                "boardStart": len(previous_board),
                "boardCards": current_board[len(previous_board):],
            }

        if not self.state.status:
            self.message = "Van bai ket thuc - chu ban co the chia van moi"
            self.last_event = {**self.last_event, "finished": True}
            if not self.result_recorded:
                try:
                    record_hand_result(self)
                except Exception as exc:
                    print(f"Could not record hand result: {exc}")
                self.result_recorded = True


rooms: dict[str, Room] = {}


def make_room_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if code not in rooms:
            return code


def cards_to_strings(cards):
    return [repr(card) for card in cards]


def board_strings(state):
    return cards_to_strings(card for board_cards in state.board_cards for card in board_cards)


def room_payload(room: Room, viewer_id: str):
    viewer_seat = room.seat_of(viewer_id)
    state = room.state
    playing = state is not None
    finished = playing and not state.status
    players = []

    for seat, player in enumerate(room.players):
        hole = []
        showdown_reveal = finished and seat not in room.folded_seats
        if showdown_reveal and seat < len(room.dealt_hole_cards):
            hole = room.dealt_hole_cards[seat]
        elif playing and seat == viewer_seat:
            hole = cards_to_strings(state.hole_cards[seat])

        players.append({
            "id": player.player_id,
            "name": player.name,
            "seat": seat,
            "connected": player.connected,
            "chips": state.stacks[seat] if playing else 1000,
            "bet": state.bets[seat] if playing and state.status else 0,
            "active": state.statuses[seat] if playing else True,
            "folded": seat in room.folded_seats,
            "winner": bool(playing and not state.status and state.payoffs[seat] > 0),
            "payoff": int(state.payoffs[seat]) if playing and not state.status else 0,
            "cards": hole,
        })

    actor = state.actor_index if playing and state.status else None
    minimum = 0
    maximum = 0
    if actor is not None:
        minimum = state.min_completion_betting_or_raising_to_amount or max(state.bets)
        maximum = state.max_completion_betting_or_raising_to_amount or minimum

    return {
        "type": "state",
        "room": room.code,
        "viewerSeat": viewer_seat,
        "host": room.host_id() == viewer_id,
        "hand": room.hand_number,
        "message": room.message,
        "started": playing,
        "finished": finished,
        "actor": actor,
        "pot": state.total_pot_amount if playing else 0,
        "board": board_strings(state) if playing else [],
        "players": players,
        "minRaise": minimum,
        "maxRaise": maximum,
        "lastEvent": room.last_event,
    }


async def broadcast(room):
    for player in room.players:
        if player.socket and player.connected:
            try:
                await player.socket.send_json(room_payload(room, player.player_id))
            except Exception:
                player.connected = False


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/rooms")
async def create_room():
    code = make_room_code()
    rooms[code] = Room(code)
    return {"code": code}


@app.get("/health")
async def health():
    return {"status": "ok", "rooms": len(rooms)}


@app.get("/api/rooms/{room_code}/history")
async def get_room_history(room_code: str, limit: int = 20):
    return {"room": room_code.upper(), "hands": room_history(room_code, limit)}


@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_room(websocket: WebSocket, room_code: str, player_id: str):
    await websocket.accept()
    room_code = room_code.upper()
    room = rooms.get(room_code)
    if room is None:
        if room_code == DEFAULT_ROOM_CODE:
            room = rooms[room_code] = Room(room_code)
        else:
            await websocket.send_json({"type": "error", "message": "Khong tim thay phong"})
            await websocket.close()
            return

    fallback_name = f"Player {player_id[-4:].upper()}"
    name = websocket.query_params.get("name", fallback_name).strip()[:18] or fallback_name
    player = next((p for p in room.players if p.player_id == player_id), None)
    if player is None:
        if room.state is not None and room.state.status:
            await websocket.send_json({"type": "error", "message": "Van dang choi, hay cho van sau"})
            await websocket.close()
            return
        if len(room.players) >= 6:
            await websocket.send_json({"type": "error", "message": "Ban da du 6 nguoi"})
            await websocket.close()
            return
        player = Player(player_id, name, websocket)
        room.players.append(player)
    else:
        player.socket, player.connected, player.name = websocket, True, name

    room.message = f"{name} da vao ban"
    await broadcast(room)
    try:
        while True:
            try:
                data = json.loads(await websocket.receive_text())
                if data.get("type") == "start":
                    if room.host_id() != player_id:
                        raise ValueError("Chi chu ban duoc bat dau")
                    room.start_hand()
                elif data.get("type") == "action":
                    room.act(room.seat_of(player_id), data.get("action"), data.get("amount"))
                elif data.get("type") == "rename":
                    player.name = str(data.get("name") or player.name).strip()[:18] or player.name
                    room.message = f"{player.name} da doi ten"
                else:
                    raise ValueError("Yeu cau khong hop le")
                await broadcast(room)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        player.connected = False
        room.message = f"{player.name} da mat ket noi"
        await broadcast(room)
