import unittest

from main import evaluate


class TestHandEvaluation(unittest.TestCase):
    def test_straight_flush_beats_quads(self):
        straight_flush = [(10, "♥"), (11, "♥"), (12, "♥"), (13, "♥"), (14, "♥"), (2, "♣"), (3, "♦")]
        quads = [(9, "♥"), (9, "♦"), (9, "♣"), (9, "♠"), (14, "♥"), (2, "♣"), (3, "♦")]
        self.assertGreater(evaluate(straight_flush), evaluate(quads))

    def test_wheel_straight(self):
        cards = [(14, "♠"), (2, "♥"), (3, "♦"), (4, "♣"), (5, "♠"), (9, "♥"), (10, "♦")]
        self.assertEqual(evaluate(cards)[:2], (4, 5))

    def test_two_pair_kicker(self):
        first = [(14, "♠"), (14, "♥"), (8, "♠"), (8, "♥"), (13, "♣"), (2, "♦"), (3, "♣")]
        second = [(14, "♦"), (14, "♣"), (8, "♦"), (8, "♣"), (12, "♣"), (2, "♠"), (3, "♦")]
        self.assertGreater(evaluate(first), evaluate(second))


if __name__ == "__main__":
    unittest.main()
