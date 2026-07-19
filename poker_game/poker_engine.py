"""PokerKit adapter used by the UI and future multiplayer server.

Keeping PokerKit behind this small boundary lets the Pygame presentation evolve
independently from the rules engine. The browser build can still start with the
legacy evaluator if its Python runtime cannot load third-party packages.
"""

try:
    from pokerkit import Automation, NoLimitTexasHoldem, StandardHighHand

    POKERKIT_AVAILABLE = True
except ImportError:  # pragma: no cover - browser fallback
    Automation = NoLimitTexasHoldem = StandardHighHand = None
    POKERKIT_AVAILABLE = False


RANK_CODES = {10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}
SUIT_CODES = {"♠": "s", "♥": "h", "♦": "d", "♣": "c"}
LABEL_CATEGORIES = {
    "High card": 0,
    "One pair": 1,
    "Two pair": 2,
    "Three of a kind": 3,
    "Straight": 4,
    "Flush": 5,
    "Full house": 6,
    "Four of a kind": 7,
    "Straight flush": 8,
}


def card_code(card):
    rank, suit = card
    return f"{RANK_CODES.get(rank, rank)}{SUIT_CODES[suit]}"


def evaluate_cards(cards):
    """Return a comparable ``(category, PokerKit rank)`` tuple or ``None``."""
    if not POKERKIT_AVAILABLE or len(cards) < 5:
        return None
    codes = [card_code(card) for card in cards]
    hand = StandardHighHand.from_game("".join(codes[:2]), "".join(codes[2:]))
    label = hand.entry.label.value
    return LABEL_CATEGORIES[label], hand.entry.index


def create_holdem_state(stacks, blinds=(10, 20), minimum_bet=20):
    """Create a server-authoritative PokerKit state for a future online table."""
    if not POKERKIT_AVAILABLE:
        raise RuntimeError("PokerKit is not installed")
    automations = (
        Automation.ANTE_POSTING,
        Automation.BET_COLLECTION,
        Automation.BLIND_OR_STRADDLE_POSTING,
        Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
        Automation.HAND_KILLING,
        Automation.CHIPS_PUSHING,
        Automation.CHIPS_PULLING,
    )
    return NoLimitTexasHoldem.create_state(
        automations,
        True,
        0,
        blinds,
        minimum_bet,
        tuple(stacks),
        len(stacks),
    )
