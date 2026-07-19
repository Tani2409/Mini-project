import asyncio
import random
import time
from collections import Counter
from itertools import combinations

import pygame

from poker_engine import evaluate_cards


WIDTH, HEIGHT = 1100, 720
FPS = 60
GREEN = (20, 105, 66)
DARK_GREEN = (12, 67, 44)
GOLD = (239, 190, 72)
WHITE = (245, 245, 240)
BLACK = (24, 27, 31)
RED = (194, 47, 55)
BLUE = (45, 93, 160)
GRAY = (112, 122, 126)
UI_FONT = "cambria"
DEALER_CENTER = (550, 137)
BOT_CARD_POS = (716, 105)

CHIP_DENOMINATIONS = [
    (100, (32, 38, 43)),
    (25, (39, 111, 184)),
    (10, (194, 47, 55)),
    (5, (224, 174, 45)),
    (1, (235, 235, 225)),
]

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = list(range(2, 15))
RANK_TEXT = {11: "J", 12: "Q", 13: "K", 14: "A"}
HAND_NAMES = [
    "Mậu thầu", "Một đôi", "Hai đôi", "Bộ ba", "Sảnh",
    "Thùng", "Cù lũ", "Tứ quý", "Thùng phá sảnh",
]


class Button:
    def __init__(self, rect, text, color):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.enabled = True

    def draw(self, screen, font, mouse):
        color = self.color if self.enabled else GRAY
        if self.enabled and self.rect.collidepoint(mouse):
            color = tuple(min(255, c + 25) for c in color)
        shadow = self.rect.move(0, 5)
        pygame.draw.rect(screen, (7, 10, 12), shadow, border_radius=12)
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        highlight = pygame.Rect(self.rect.x + 4, self.rect.y + 4, self.rect.w - 8, self.rect.h // 2)
        pygame.draw.rect(screen, tuple(min(255, c + 18) for c in color), highlight, border_radius=9)
        pygame.draw.rect(screen, (224, 196, 116), self.rect, 2, border_radius=12)
        label = font.render(self.text, True, WHITE)
        screen.blit(label, label.get_rect(center=self.rect.center))


class BetSlider:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.dragging = False

    def value_from_x(self, x, minimum, maximum):
        if maximum <= minimum:
            return minimum
        ratio = max(0.0, min(1.0, (x - self.rect.left) / self.rect.width))
        raw = minimum + ratio * (maximum - minimum)
        if ratio >= 0.99:
            return maximum
        return minimum + int((raw - minimum) / 10) * 10

    def draw(self, screen, font, small, minimum, maximum, value):
        pygame.draw.rect(screen, (5, 14, 17), self.rect.inflate(10, 18), border_radius=12)
        pygame.draw.line(screen, (91, 103, 106), self.rect.midleft, self.rect.midright, 7)
        ratio = 0 if maximum <= minimum else (value - minimum) / (maximum - minimum)
        knob_x = int(self.rect.left + max(0, min(1, ratio)) * self.rect.width)
        pygame.draw.line(screen, GOLD, self.rect.midleft, (knob_x, self.rect.centery), 7)
        pygame.draw.circle(screen, (8, 12, 15), (knob_x + 2, self.rect.centery + 3), 13)
        pygame.draw.circle(screen, GOLD, (knob_x, self.rect.centery), 12)
        pygame.draw.circle(screen, WHITE, (knob_x, self.rect.centery), 5)
        selected = font.render(f"CƯỢC: {value}", True, GOLD)
        screen.blit(selected, selected.get_rect(center=(self.rect.centerx, self.rect.top - 17)))
        left = small.render(f"THEO {minimum}", True, WHITE)
        right = small.render(f"ALL-IN {maximum}", True, WHITE)
        screen.blit(left, (self.rect.left, self.rect.bottom + 5))
        screen.blit(right, right.get_rect(topright=(self.rect.right, self.rect.bottom + 5)))


def make_deck():
    deck = [(rank, suit) for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def evaluate_five(cards):
    ranks = sorted((rank for rank, _ in cards), reverse=True)
    counts = Counter(ranks)
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    flush = len({suit for _, suit in cards}) == 1
    unique = sorted(set(ranks), reverse=True)
    if 14 in unique:
        unique.append(1)
    straight_high = next(
        (unique[i] for i in range(len(unique) - 4)
         if unique[i] - unique[i + 4] == 4), 0
    )

    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(rank for rank in ranks if rank != quad)
        return (7, quad, kicker)
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if groups[0][0] == 3:
        trip = groups[0][1]
        kickers = sorted((r for r in ranks if r != trip), reverse=True)
        return (3, trip, *kickers)
    pairs = sorted((rank for count, rank in groups if count == 2), reverse=True)
    if len(pairs) >= 2:
        kicker = max(r for r in ranks if r not in pairs[:2])
        return (2, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((r for r in ranks if r != pair), reverse=True)
        return (1, pair, *kickers)
    return (0, *ranks)


def evaluate(cards):
    pokerkit_result = evaluate_cards(cards)
    if pokerkit_result is not None:
        return pokerkit_result
    return max(evaluate_five(list(combo)) for combo in combinations(cards, 5))


class PokerGame:
    def __init__(self):
        self.player_chips = 1000
        self.bot_chips = 1000
        self.dealer_is_player = False
        self.message = ""
        self.new_hand()

    def new_hand(self):
        if self.player_chips <= 0 or self.bot_chips <= 0:
            self.player_chips = self.bot_chips = 1000
        self.deck = make_deck()
        self.player = [self.deck.pop(), self.deck.pop()]
        self.bot = [self.deck.pop(), self.deck.pop()]
        self.community = []
        self.pot = 0
        self.player_bet = 0
        self.bot_bet = 0
        self.stage = 0
        self.raise_amount = 20
        self.finished = False
        self.reveal_bot = False
        self.visible_player = 0
        self.visible_bot = 0
        self.visible_community = 0
        self.chip_animations = []
        self.deal_queue = [
            ("player", 0), ("bot", 0), ("player", 1), ("bot", 1)
        ]
        self.animation = None
        self.next_deal_at = time.monotonic() + 0.35
        self.dealer_is_player = not self.dealer_is_player
        if self.dealer_is_player:
            self._put_player(10)
            self._put_bot(20)
        else:
            self._put_bot(10)
            self._put_player(20)
        self.message = "Lượt của bạn"

    @property
    def animating(self):
        return self.animation is not None or bool(self.deal_queue)

    def queue_community_cards(self, first_index, count):
        self.deal_queue.extend(("community", first_index + i) for i in range(count))
        self.next_deal_at = time.monotonic() + 0.25

    def update_animation(self):
        now = time.monotonic()
        self.chip_animations = [
            chip for chip in self.chip_animations
            if now - chip["start"] < chip["duration"]
        ]
        if self.animation:
            elapsed = now - self.animation["start"]
            if elapsed >= 0.38:
                target = self.animation["target"]
                if target == "player":
                    self.visible_player += 1
                elif target == "bot":
                    self.visible_bot += 1
                else:
                    self.visible_community += 1
                self.animation = None
                self.next_deal_at = now + 0.08
        elif self.deal_queue and now >= self.next_deal_at:
            target, index = self.deal_queue.pop(0)
            self.animation = {"target": target, "index": index, "start": now}

    def _put_player(self, amount):
        amount = min(amount, self.player_chips)
        if amount <= 0:
            return
        self.player_chips -= amount
        self.player_bet += amount
        self.pot += amount
        self._animate_chips(amount, "player")

    def _put_bot(self, amount):
        amount = min(amount, self.bot_chips)
        if amount <= 0:
            return
        self.bot_chips -= amount
        self.bot_bet += amount
        self.pot += amount
        self._animate_chips(amount, "bot")

    def _animate_chips(self, amount, owner):
        """Create a short stream of representative chips moving into the pot."""
        chips = []
        remainder = amount
        for value, color in CHIP_DENOMINATIONS:
            count, remainder = divmod(remainder, value)
            chips.extend((value, color) for _ in range(min(count, 3)))

        now = time.monotonic()
        for index, (value, color) in enumerate(chips[:8]):
            self.chip_animations.append({
                "owner": owner,
                "value": value,
                "color": color,
                "start": now + index * 0.055,
                "duration": 0.52,
                "offset": random.randint(-10, 10),
            })

    @property
    def to_call(self):
        return max(0, self.bot_bet - self.player_bet)

    @property
    def max_raise(self):
        return max(0, self.player_chips - self.to_call)

    def adjust_raise(self, change):
        if self.finished or self.animating:
            return
        maximum = self.max_raise
        if maximum <= 0:
            self.raise_amount = 0
        else:
            self.raise_amount = max(10, min(maximum, self.raise_amount + change))

    def player_action(self, action):
        if self.finished or self.animating:
            return
        if action == "fold":
            self.bot_chips += self.pot
            self.pot = 0
            self.finished = True
            self.reveal_bot = True
            self.message = "Bạn bỏ bài - Máy thắng"
            return
        if action == "call":
            self._put_player(self.to_call)
            self.message = "Bạn theo cược"
        elif action == "raise":
            amount = min(self.raise_amount, self.max_raise)
            self._put_player(self.to_call + amount)
            self.message = f"Bạn tăng {amount} chip" if amount else "Bạn theo cược"
        elif action == "allin":
            amount = self.max_raise
            self._put_player(self.player_chips)
            self.message = f"Bạn ALL-IN, tăng {amount} chip"
        self.bot_turn(action in ("raise", "allin"))

    def bot_turn(self, facing_raise=False):
        score = evaluate(self.bot + self.community) if len(self.community) >= 3 else None
        strength = score[0] if score else max(card[0] for card in self.bot) / 14
        call = max(0, self.player_bet - self.bot_bet)
        fold_chance = 0.28 if facing_raise and strength < 1 else 0.03
        if call and random.random() < fold_chance:
            self.player_chips += self.pot
            self.pot = 0
            self.finished = True
            self.reveal_bot = True
            self.message = "Máy bỏ bài - Bạn thắng!"
            return
        self._put_bot(call)
        self.advance_stage()

    def advance_stage(self):
        self.player_bet = self.bot_bet = 0
        self.stage += 1
        if self.stage == 1:
            self.community.extend([self.deck.pop() for _ in range(3)])
            self.queue_community_cards(0, 3)
            self.message = "Flop - lượt của bạn"
        elif self.stage == 2:
            self.community.append(self.deck.pop())
            self.queue_community_cards(3, 1)
            self.message = "Turn - lượt của bạn"
        elif self.stage == 3:
            self.community.append(self.deck.pop())
            self.queue_community_cards(4, 1)
            self.message = "River - lượt của bạn"
        else:
            self.showdown()

    def showdown(self):
        self.finished = True
        self.reveal_bot = True
        player_score = evaluate(self.player + self.community)
        bot_score = evaluate(self.bot + self.community)
        if player_score > bot_score:
            self.player_chips += self.pot
            self.message = f"Bạn thắng với {HAND_NAMES[player_score[0]]}!"
        elif bot_score > player_score:
            self.bot_chips += self.pot
            self.message = f"Máy thắng với {HAND_NAMES[bot_score[0]]}"
        else:
            half = self.pot // 2
            self.player_chips += half
            self.bot_chips += self.pot - half
            self.message = "Hòa - chia pot"
        self.pot = 0


def draw_card(screen, card, x, y, hidden=False):
    rect = pygame.Rect(x, y, 82, 116)
    pygame.draw.rect(screen, (6, 20, 15), rect.move(5, 7), border_radius=11)
    pygame.draw.rect(screen, WHITE if not hidden else BLUE, rect, border_radius=9)
    pygame.draw.rect(screen, (211, 174, 80), rect, 2, border_radius=9)
    if hidden:
        inner = rect.inflate(-10, -10)
        pygame.draw.rect(screen, (27, 65, 126), inner, border_radius=6)
        for offset in range(8, 76, 12):
            pygame.draw.line(screen, (90, 145, 205), (x + offset, y + 7),
                             (x + 7, y + offset), 2)
        pygame.draw.circle(screen, GOLD, rect.center, 17, 2)
        pygame.draw.circle(screen, GOLD, rect.center, 8, 2)
        return
    rank, suit = card
    color = RED if suit in ("♥", "♦") else BLACK
    rank_label = RANK_TEXT.get(rank, str(rank))
    font = pygame.font.SysFont(UI_FONT, 25, bold=True)
    suit_font = pygame.font.SysFont("segoeuisymbol", 35)
    screen.blit(font.render(rank_label, True, color), (x + 9, y + 5))
    symbol = suit_font.render(suit, True, color)
    screen.blit(symbol, symbol.get_rect(center=(x + 42, y + 66)))
    mini = suit_font.render(suit, True, color)
    mini = pygame.transform.smoothscale(mini, (18, 20))
    screen.blit(mini, (x + 55, y + 91))


def create_casino_background():
    surface = pygame.Surface((WIDTH, HEIGHT))
    top = (16, 20, 28)
    bottom = (5, 8, 12)
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (WIDTH, y))
    rng = random.Random(2409)
    for _ in range(150):
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        shade = rng.choice([(31, 34, 42), (22, 27, 34), (45, 38, 26)])
        pygame.draw.circle(surface, shade, (x, y), rng.choice((1, 1, 2)))
    return surface


def draw_casino_table(screen):
    # Bóng, thành gỗ, nẹp vàng và lớp nỉ tạo chiều sâu cho bàn.
    pygame.draw.ellipse(screen, (2, 5, 6), (73, 52, 954, 570))
    pygame.draw.ellipse(screen, (55, 27, 18), (76, 37, 948, 574))
    pygame.draw.ellipse(screen, (111, 63, 29), (82, 43, 936, 558), 6)
    pygame.draw.ellipse(screen, GOLD, (88, 49, 924, 546))
    pygame.draw.ellipse(screen, (10, 68, 47), (96, 57, 908, 530))
    pygame.draw.ellipse(screen, (22, 112, 74), (108, 69, 884, 506), 3)
    # Texture nỉ cố định theo tọa độ, không nhấp nháy giữa các frame.
    for i in range(85):
        x = 135 + (i * 97) % 820
        y = 92 + (i * 53) % 450
        if ((x - 550) / 442) ** 2 + ((y - 322) / 253) ** 2 < 0.94:
            pygame.draw.circle(screen, (27, 119, 79), (x, y), 1)


def draw_dealer(screen, font, small):
    """Vẽ dealer hoạt hình đơn giản, không cần file ảnh bên ngoài."""
    x, y = DEALER_CENTER
    # Ghế tròn nằm trong hốc dealer.
    pygame.draw.circle(screen, (45, 20, 17), (x, y + 21), 67)
    pygame.draw.circle(screen, (151, 98, 42), (x, y + 21), 67, 3)
    pygame.draw.circle(screen, (18, 23, 27), (x, y + 21), 59)
    # Thân người được thu gọn để dealer ngồi sau mép bàn.
    pygame.draw.polygon(screen, BLACK, [(x - 55, y + 82), (x - 40, y + 34),
                                        (x + 40, y + 34), (x + 55, y + 82)])
    pygame.draw.polygon(screen, WHITE, [(x - 24, y + 35), (x, y + 70), (x + 24, y + 35)])
    pygame.draw.polygon(screen, RED, [(x - 6, y + 47), (x + 6, y + 47),
                                      (x + 9, y + 68), (x, y + 77), (x - 9, y + 68)])
    pygame.draw.circle(screen, (242, 196, 154), (x, y), 38)
    pygame.draw.arc(screen, BLACK, (x - 37, y - 39, 74, 45), 3.25, 6.15, 15)
    pygame.draw.circle(screen, BLACK, (x - 13, y - 3), 4)
    pygame.draw.circle(screen, BLACK, (x + 13, y - 3), 4)
    pygame.draw.arc(screen, (130, 54, 46), (x - 12, y + 4, 24, 16), 0.1, 3.0, 2)
    badge = small.render("DEALER", True, BLACK)
    badge_box = pygame.Rect(x - 38, y + 78, 76, 25)
    pygame.draw.rect(screen, GOLD, badge_box, border_radius=7)
    screen.blit(badge, badge.get_rect(center=badge_box.center))


def draw_chip(screen, x, y, color, value=None, scale=1.0):
    """Vẽ một chip poker có viền và các vạch trang trí."""
    radius = int(19 * scale)
    pygame.draw.circle(screen, (16, 20, 24), (x + 2, y + 3), radius + 2)
    pygame.draw.circle(screen, color, (x, y), radius)
    pygame.draw.circle(screen, WHITE, (x, y), radius, max(2, int(3 * scale)))
    pygame.draw.circle(screen, color, (x, y), int(radius * 0.58))
    pygame.draw.circle(screen, WHITE, (x, y), int(radius * 0.42), max(1, int(2 * scale)))
    for angle in range(0, 360, 45):
        vector = pygame.Vector2(0, -radius * 0.78).rotate(angle)
        pygame.draw.circle(screen, WHITE, (int(x + vector.x), int(y + vector.y)), max(2, int(3 * scale)))
    if value is not None:
        chip_font = pygame.font.SysFont(UI_FONT, max(9, int(11 * scale)), bold=True)
        label = chip_font.render(str(value), True, WHITE)
        screen.blit(label, label.get_rect(center=(x, y)))


def draw_chip_stack(screen, x, y, amount, label, font, small):
    # Mỗi mệnh giá có một màu và một cột riêng. Chia từ chip lớn xuống nhỏ.
    remainder = amount
    stacks = []
    for value, color in CHIP_DENOMINATIONS:
        count, remainder = divmod(remainder, value)
        if count:
            stacks.append((value, color, count))

    spacing = 35
    first_x = x - ((len(stacks) - 1) * spacing) // 2
    for column, (value, color, count) in enumerate(stacks):
        chip_x = first_x + column * spacing
        visible_count = min(10, count)
        for i in range(visible_count):
            draw_chip(screen, chip_x, y - i * 6, color, value, 0.72)
        if count > visible_count:
            count_text = small.render(f"×{count}", True, WHITE)
            screen.blit(count_text, count_text.get_rect(center=(chip_x, y - visible_count * 6 - 15)))
    if label:
        text = small.render(f"{label}: {amount}", True, WHITE if label != "POT" else GOLD)
        screen.blit(text, text.get_rect(center=(x, y + 36)))


def draw_chip_animations(screen, game):
    now = time.monotonic()
    for chip in game.chip_animations:
        progress = (now - chip["start"]) / chip["duration"]
        if progress < 0:
            continue
        progress = min(1.0, progress)
        eased = 1 - (1 - progress) ** 3
        start = (765, 520) if chip["owner"] == "player" else (925, 225)
        end = (250 + chip["offset"], 252 + chip["offset"] // 3)
        x = start[0] + (end[0] - start[0]) * eased
        y = start[1] + (end[1] - start[1]) * eased
        y -= 30 * (4 * progress * (1 - progress))
        scale = 0.82 + 0.18 * progress
        draw_chip(screen, int(x), int(y), chip["color"], chip["value"], scale)


def animation_position(game):
    anim = game.animation
    if not anim:
        return None
    progress = min(1.0, (time.monotonic() - anim["start"]) / 0.38)
    progress = 1 - (1 - progress) ** 3
    start = (DEALER_CENTER[0] + 32, DEALER_CENTER[1] + 75)
    if anim["target"] == "player":
        end = (458 + anim["index"] * 92, 470)
    elif anim["target"] == "bot":
        end = (BOT_CARD_POS[0] + anim["index"] * 92, BOT_CARD_POS[1])
    else:
        total_width = len(game.community) * 92 - 10
        start_x = WIDTH // 2 - total_width // 2
        end = (start_x + anim["index"] * 92, 310)
    x = start[0] + (end[0] - start[0]) * progress
    y = start[1] + (end[1] - start[1]) * progress - 45 * (4 * progress * (1 - progress))
    return int(x), int(y)


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("POKER")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(UI_FONT, 23, bold=True)
    small = pygame.font.SysFont(UI_FONT, 18)
    background = create_casino_background()
    game = PokerGame()
    bet_slider = BetSlider((700, 610, 310, 8))
    buttons = {
        "fold": Button((165, 662, 125, 45), "FOLD", (151, 48, 55)),
        "call": Button((300, 662, 165, 45), "CHECK / CALL", (36, 109, 170)),
        "raise": Button((475, 662, 180, 45), "CƯỢC", (178, 119, 34)),
        "allin": Button((665, 662, 115, 45), "ALL-IN", (126, 51, 153)),
        "new": Button((790, 662, 140, 45), "VÁN MỚI", (52, 133, 80)),
    }

    running = True
    while running:
        game.update_animation()
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                slider_hitbox = bet_slider.rect.inflate(24, 32)
                if not game.finished and not game.animating and slider_hitbox.collidepoint(event.pos):
                    bet_slider.dragging = True
                    minimum = min(game.to_call, game.player_chips)
                    total = bet_slider.value_from_x(event.pos[0], minimum, game.player_chips)
                    game.raise_amount = max(0, total - game.to_call)
                else:
                    for action, button in buttons.items():
                        if button.enabled and button.rect.collidepoint(event.pos):
                            game.new_hand() if action == "new" else game.player_action(action)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                bet_slider.dragging = False
            if event.type == pygame.MOUSEMOTION and bet_slider.dragging:
                minimum = min(game.to_call, game.player_chips)
                total = bet_slider.value_from_x(event.pos[0], minimum, game.player_chips)
                game.raise_amount = max(0, total - game.to_call)

        screen.blit(background, (0, 0))
        draw_casino_table(screen)
        bot_panel = pygame.Rect(708, 59, 210, 36)
        pygame.draw.rect(screen, (8, 43, 31), bot_panel, border_radius=18)
        pygame.draw.rect(screen, (92, 151, 112), bot_panel, 1, border_radius=18)
        bot_text = font.render(f"MÁY: {game.bot_chips} chip", True, WHITE)
        screen.blit(bot_text, bot_text.get_rect(center=bot_panel.center))
        draw_dealer(screen, font, small)
        draw_chip_stack(screen, 925, 245, game.bot_chips, "CHIP MÁY", font, small)
        draw_chip_stack(screen, 765, 535, game.player_chips, "CHIP BẠN", font, small)
        draw_chip_stack(screen, 250, 270, game.pot, "", font, small)
        draw_chip_animations(screen, game)

        for i, card in enumerate(game.bot[:game.visible_bot]):
            draw_card(screen, card, BOT_CARD_POS[0] + i * 92, BOT_CARD_POS[1], not game.reveal_bot)
        start_x = WIDTH // 2 - (len(game.community) * 92 - 10) // 2
        for i, card in enumerate(game.community[:game.visible_community]):
            draw_card(screen, card, start_x + i * 92, 310)
        pot_panel = pygame.Rect(WIDTH // 2 - 92, 433, 184, 31)
        pygame.draw.rect(screen, (8, 52, 36), pot_panel, border_radius=15)
        pygame.draw.rect(screen, GOLD, pot_panel, 1, border_radius=15)
        pot_text = font.render(f"POT  •  {game.pot}", True, GOLD)
        screen.blit(pot_text, pot_text.get_rect(center=pot_panel.center))
        for i, card in enumerate(game.player[:game.visible_player]):
            draw_card(screen, card, 458 + i * 92, 470)

        moving = animation_position(game)
        if moving:
            target = game.animation["target"]
            index = game.animation["index"]
            if target == "player":
                moving_card, hidden = game.player[index], False
            elif target == "bot":
                moving_card, hidden = game.bot[index], True
            else:
                moving_card, hidden = game.community[index], False
            draw_card(screen, moving_card, *moving, hidden=hidden)

        player_panel = pygame.Rect(432, 588, 236, 37)
        pygame.draw.rect(screen, (8, 43, 31), player_panel, border_radius=18)
        pygame.draw.rect(screen, (92, 151, 112), player_panel, 1, border_radius=18)
        player_label = font.render(f"BẠN: {game.player_chips} chip", True, WHITE)
        screen.blit(player_label, player_label.get_rect(center=player_panel.center))
        status = font.render(game.message, True, GOLD)
        status_panel = pygame.Rect(WIDTH // 2 - max(125, status.get_width() // 2 + 18), 274,
                                   max(250, status.get_width() + 36), 35)
        pygame.draw.rect(screen, (5, 45, 31), status_panel, border_radius=17)
        pygame.draw.rect(screen, (146, 119, 52), status_panel, 1, border_radius=17)
        screen.blit(status, status.get_rect(center=status_panel.center))
        if not game.finished and game.to_call:
            call_text = small.render(f"Cần theo: {game.to_call} chip", True, WHITE)
            screen.blit(call_text, (85, 650))

        slider_min = min(game.to_call, game.player_chips)
        slider_max = game.player_chips
        slider_total = min(slider_max, slider_min + game.raise_amount)
        game.raise_amount = max(0, slider_total - game.to_call)
        bet_slider.draw(screen, font, small, slider_min, slider_max, slider_total)
        buttons["raise"].text = f"CƯỢC {slider_total}"
        for key in ("fold", "call", "raise", "allin"):
            buttons[key].enabled = not game.finished and not game.animating
        buttons["raise"].enabled = buttons["raise"].enabled and game.player_chips > 0
        buttons["allin"].enabled = buttons["allin"].enabled and game.player_chips > 0
        buttons["new"].enabled = game.finished
        for button in buttons.values():
            button.draw(screen, font, mouse)

        pygame.display.flip()
        clock.tick(FPS)
        # Trả quyền điều khiển cho event loop; bắt buộc khi chạy WebAssembly.
        await asyncio.sleep(0)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
