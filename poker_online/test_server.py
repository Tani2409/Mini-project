import unittest
import os

os.environ.setdefault("POKER_DATABASE_URL", "sqlite:///test_poker_history.db")

from fastapi.testclient import TestClient

from server import DEFAULT_ROOM_CODE, Player, Room, app, room_payload, rooms


class TestOnlineRoom(unittest.TestCase):
    def setUp(self):
        self.room = Room("ABCDE", [Player("a", "An"), Player("b", "Binh")])
        self.room.start_hand()

    def test_private_cards_are_hidden(self):
        payload = room_payload(self.room, "a")
        self.assertEqual(len(payload["players"][0]["cards"]), 2)
        self.assertEqual(payload["players"][1]["cards"], [])

    def test_two_calls_deal_flop(self):
        self.room.act(self.room.state.actor_index, "call")
        self.room.act(self.room.state.actor_index, "call")
        payload = room_payload(self.room, "a")
        self.assertEqual(len(payload["board"]), 3)
        self.assertTrue(all(len(card) == 2 for card in payload["board"]))

    def test_raise_passes_turn_to_next_player(self):
        raiser = self.room.state.actor_index
        self.room.act(raiser, "raise", 40)
        payload = room_payload(self.room, "a")

        self.assertNotEqual(payload["actor"], raiser)
        self.assertEqual(payload["lastEvent"]["kind"], "raise")

    def test_wrong_seat_cannot_act(self):
        wrong_seat = 1 - self.room.state.actor_index
        with self.assertRaises(ValueError):
            self.room.act(wrong_seat, "fold")

    def test_finished_hand_reveals_all_hole_cards(self):
        folder = self.room.state.actor_index
        self.room.act(folder, "fold")
        payload = room_payload(self.room, "a")

        self.assertTrue(payload["finished"])
        self.assertTrue(any(player["winner"] for player in payload["players"]))
        self.assertTrue(any(len(player["cards"]) == 2 for player in payload["players"]))

    def test_showdown_reveals_all_non_folded_players(self):
        limit = 20
        while self.room.state.status and limit:
            self.room.act(self.room.state.actor_index, "call")
            limit -= 1

        payload = room_payload(self.room, "a")

        self.assertTrue(payload["finished"])
        self.assertTrue(all(not player["folded"] for player in payload["players"]))
        self.assertTrue(all(len(player["cards"]) == 2 for player in payload["players"]))

    def test_history_records_finished_hand(self):
        self.room.act(self.room.state.actor_index, "fold")
        client = TestClient(app)
        response = client.get("/api/rooms/ABCDE/history")

        self.assertEqual(response.status_code, 200)
        hands = response.json()["hands"]
        self.assertGreaterEqual(len(hands), 1)
        self.assertTrue(any(player["winner"] for player in hands[0]["players"]))


class TestOnlineApp(unittest.TestCase):
    def test_home_health_and_room_creation(self):
        client = TestClient(app)
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/health").json()["status"], "ok")
        code = client.post("/api/rooms").json()["code"]
        self.assertEqual(len(code), 5)

    def test_default_table_is_created_on_connect(self):
        rooms.pop(DEFAULT_ROOM_CODE, None)
        client = TestClient(app)

        with client.websocket_connect(f"/ws/{DEFAULT_ROOM_CODE}/player-a?name=An") as socket:
            payload = socket.receive_json()

        self.assertEqual(payload["room"], DEFAULT_ROOM_CODE)
        self.assertTrue(payload["host"])


if __name__ == "__main__":
    unittest.main()
