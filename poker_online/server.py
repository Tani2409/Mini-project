import json
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pokerkit import Automation, NoLimitTexasHoldem


BASE_DIR = Path(__file__).parent
app = FastAPI(title="POKER Online")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

AUTOMATIONS = tuple(Automation)


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
    hand_number: int = 0
    message: str = "Đang chờ người chơi"
    last_event: dict = field(default_factory=dict)

    def seat_of(self, player_id):
        return next((i for i, player in enumerate(self.players) if player.player_id == player_id), None)

    def start_hand(self):
        if len(self.players) < 2:
            raise ValueError("Cần ít nhất 2 người chơi")
        if len(self.players) > 6:
            raise ValueError("Bàn đã đủ 6 người")
        stacks = tuple(self.state.stacks) if self.state is not None and not self.state.status else (1000,) * len(self.players)
        if len(stacks) != len(self.players) or sum(stack > 0 for stack in stacks) < 2:
            stacks = (1000,) * len(self.players)
        self.state = NoLimitTexasHoldem.create_state(
            AUTOMATIONS, True, 0, (10, 20), 20, stacks, len(self.players)
        )
        self.hand_number += 1
        self.dealt_hole_cards = [cards_to_strings(cards) for cards in self.state.hole_cards]
        self.message = f"Ván #{self.hand_number} bắt đầu"
        self.last_event = {"kind": "deal", "hand": self.hand_number}

    def act(self, seat, action, amount=None):
        if self.state is None or not self.state.status:
            raise ValueError("Ván bài chưa bắt đầu")
        if self.state.actor_index != seat:
            raise ValueError("Chưa đến lượt của bạn")
        if action == "fold" and self.state.can_fold():
            self.state.fold()
            self.message = f"{self.players[seat].name} đã fold"
            self.last_event = {"kind": "fold", "seat": seat}
        elif action == "call" and self.state.can_check_or_call():
            operation = self.state.check_or_call()
            self.message = f"{self.players[seat].name} check/call {operation.amount}"
            self.last_event = {"kind": "call", "seat": seat, "amount": int(operation.amount)}
        elif action == "raise":
            amount = int(amount or 0)
            if not self.state.can_complete_bet_or_raise_to(amount):
                raise ValueError("Mức raise không hợp lệ")
            self.state.complete_bet_or_raise_to(amount)
            self.message = f"{self.players[seat].name} raise tới {amount}"
            self.last_event = {"kind": "raise", "seat": seat, "amount": amount}
        else:
            raise ValueError("Hành động không hợp lệ")
        if not self.state.status:
            self.message = "Ván bài kết thúc — chủ phòng có thể chia ván mới"
            self.last_event = {**self.last_event, "finished": True}


rooms: dict[str, Room] = {}


def make_room_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if code not in rooms:
            return code


def cards_to_strings(cards):
    return [repr(card) for card in cards]


def room_payload(room: Room, viewer_id: str):
    viewer_seat = room.seat_of(viewer_id)
    state = room.state
    playing = state is not None
    finished = playing and not state.status
    players = []
    for seat, player in enumerate(room.players):
        hole = []
        if finished and seat < len(room.dealt_hole_cards):
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
            "cards": hole,
        })
    board = []
    if playing:
        board = cards_to_strings(card for board_cards in state.board_cards for card in board_cards)
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
        "host": bool(room.players and room.players[0].player_id == viewer_id),
        "hand": room.hand_number,
        "message": room.message,
        "started": playing,
        "finished": finished,
        "actor": actor,
        "pot": state.total_pot_amount if playing else 0,
        "board": board,
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


@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_room(websocket: WebSocket, room_code: str, player_id: str):
    await websocket.accept()
    room_code = room_code.upper()
    room = rooms.get(room_code)
    if room is None:
        await websocket.send_json({"type": "error", "message": "Không tìm thấy phòng"})
        await websocket.close()
        return
    name = websocket.query_params.get("name", "Người chơi").strip()[:18] or "Người chơi"
    player = next((p for p in room.players if p.player_id == player_id), None)
    if player is None:
        if room.state is not None and room.state.status:
            await websocket.send_json({"type": "error", "message": "Ván đang chơi, hãy chờ ván sau"})
            await websocket.close()
            return
        if len(room.players) >= 6:
            await websocket.send_json({"type": "error", "message": "Phòng đã đủ 6 người"})
            await websocket.close()
            return
        player = Player(player_id, name, websocket)
        room.players.append(player)
    else:
        player.socket, player.connected, player.name = websocket, True, name
    room.message = f"{name} đã vào phòng"
    await broadcast(room)
    try:
        while True:
            try:
                data = json.loads(await websocket.receive_text())
                if data.get("type") == "start":
                    if room.players[0].player_id != player_id:
                        raise ValueError("Chỉ chủ phòng được bắt đầu")
                    room.start_hand()
                elif data.get("type") == "action":
                    room.act(room.seat_of(player_id), data.get("action"), data.get("amount"))
                else:
                    raise ValueError("Yêu cầu không hợp lệ")
                await broadcast(room)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        player.connected = False
        room.message = f"{player.name} đã mất kết nối"
        await broadcast(room)
