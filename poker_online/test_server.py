import unittest

from fastapi.testclient import TestClient

from server import Player, Room, app, room_payload


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
        self.assertTrue(all(len(player["cards"]) == 2 for player in payload["players"]))


class TestOnlineApp(unittest.TestCase):
    def test_home_health_and_room_creation(self):
        client = TestClient(app)
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/health").json()["status"], "ok")
        code = client.post("/api/rooms").json()["code"]
        self.assertEqual(len(code), 5)


if __name__ == "__main__":
    unittest.main()
