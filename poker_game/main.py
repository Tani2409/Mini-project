import asyncio
import random
import time
from collections import Counter
from itertools import combinations

import pygame


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
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=12)
        label = font.render(self.text, True, WHITE)
        screen.blit(label, label.get_rect(center=self.rect.center))


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
            self.message = f"Bạn tăng {amount} chip"
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
    pygame.draw.rect(screen, WHITE if not hidden else BLUE, rect, border_radius=9)
    pygame.draw.rect(screen, GOLD, rect, 3, border_radius=9)
    if hidden:
        for offset in range(8, 76, 12):
            pygame.draw.line(screen, (90, 145, 205), (x + offset, y + 7),
                             (x + 7, y + offset), 2)
        return
    rank, suit = card
    color = RED if suit in ("♥", "♦") else BLACK
    rank_label = RANK_TEXT.get(rank, str(rank))
    font = pygame.font.SysFont("segoeui", 25, bold=True)
    suit_font = pygame.font.SysFont("segoeuisymbol", 35)
    screen.blit(font.render(rank_label, True, color), (x + 9, y + 5))
    symbol = suit_font.render(suit, True, color)
    screen.blit(symbol, symbol.get_rect(center=(x + 42, y + 66)))


def draw_dealer(screen, font, small):
    """Vẽ dealer hoạt hình đơn giản, không cần file ảnh bên ngoài."""
    x, y = 155, 245
    pygame.draw.circle(screen, (242, 196, 154), (x, y), 38)
    pygame.draw.arc(screen, BLACK, (x - 37, y - 39, 74, 45), 3.25, 6.15, 15)
    pygame.draw.circle(screen, BLACK, (x - 13, y - 3), 4)
    pygame.draw.circle(screen, BLACK, (x + 13, y - 3), 4)
    pygame.draw.arc(screen, (130, 54, 46), (x - 12, y + 4, 24, 16), 0.1, 3.0, 2)
    pygame.draw.polygon(screen, BLACK, [(105, 350), (120, 290), (190, 290), (205, 350)])
    pygame.draw.polygon(screen, WHITE, [(135, 290), (155, 330), (175, 290)])
    pygame.draw.polygon(screen, RED, [(150, 302), (160, 302), (164, 327), (155, 337), (146, 327)])
    badge = small.render("DEALER", True, BLACK)
    badge_box = pygame.Rect(120, 345, 72, 27)
    pygame.draw.rect(screen, GOLD, badge_box, border_radius=7)
    screen.blit(badge, badge.get_rect(center=badge_box.center))
    label = font.render("NHÀ CÁI", True, WHITE)
    screen.blit(label, label.get_rect(center=(155, 395)))


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
        chip_font = pygame.font.SysFont("arial", max(9, int(11 * scale)), bold=True)
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
        start = (765, 520) if chip["owner"] == "player" else (765, 210)
        end = (900 + chip["offset"], 252 + chip["offset"] // 3)
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
    start = (185, 315)
    if anim["target"] == "player":
        end = (458 + anim["index"] * 92, 470)
    elif anim["target"] == "bot":
        end = (458 + anim["index"] * 92, 95)
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
    pygame.display.set_caption("Poker Texas Hold'em")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("segoeui", 34, bold=True)
    font = pygame.font.SysFont("segoeui", 23, bold=True)
    small = pygame.font.SysFont("segoeui", 18)
    game = PokerGame()
    buttons = {
        "fold": Button((190, 640, 125, 54), "FOLD", (151, 48, 55)),
        "call": Button((325, 640, 170, 54), "CHECK / CALL", (36, 109, 170)),
        "minus": Button((505, 640, 58, 54), "−10", (91, 96, 103)),
        "raise": Button((573, 640, 165, 54), "RAISE", (178, 119, 34)),
        "plus": Button((748, 640, 58, 54), "+10", (91, 96, 103)),
        "allin": Button((816, 640, 110, 54), "ALL-IN", (126, 51, 153)),
        "new": Button((936, 640, 145, 54), "VÁN MỚI", (52, 133, 80)),
    }

    running = True
    while running:
        game.update_animation()
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for action, button in buttons.items():
                    if button.enabled and button.rect.collidepoint(event.pos):
                        if action == "new":
                            game.new_hand()
                        elif action == "minus":
                            game.adjust_raise(-10)
                        elif action == "plus":
                            game.adjust_raise(10)
                        else:
                            game.player_action(action)

        screen.fill(DARK_GREEN)
        pygame.draw.ellipse(screen, GREEN, (85, 45, 930, 560))
        pygame.draw.ellipse(screen, GOLD, (85, 45, 930, 560), 5)
        screen.blit(title_font.render("TEXAS HOLD'EM", True, GOLD), (28, 18))
        screen.blit(font.render(f"MÁY: {game.bot_chips} chip", True, WHITE), (455, 65))
        draw_dealer(screen, font, small)
        draw_chip_stack(screen, 765, 225, game.bot_chips, "CHIP MÁY", font, small)
        draw_chip_stack(screen, 765, 535, game.player_chips, "CHIP BẠN", font, small)
        draw_chip_stack(screen, 900, 270, game.pot, "POT", font, small)
        draw_chip_animations(screen, game)

        for i, card in enumerate(game.bot[:game.visible_bot]):
            draw_card(screen, card, 458 + i * 92, 95, not game.reveal_bot)
        start_x = WIDTH // 2 - (len(game.community) * 92 - 10) // 2
        for i, card in enumerate(game.community[:game.visible_community]):
            draw_card(screen, card, start_x + i * 92, 310)
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

        player_label = font.render(f"BẠN: {game.player_chips} chip", True, WHITE)
        screen.blit(player_label, (455, 595))
        status = font.render(game.message, True, GOLD)
        screen.blit(status, status.get_rect(center=(WIDTH // 2, 292)))
        if not game.finished and game.to_call:
            call_text = small.render(f"Cần theo: {game.to_call} chip", True, WHITE)
            screen.blit(call_text, (85, 650))

        buttons["raise"].text = f"RAISE {game.raise_amount}"
        for key in ("fold", "call", "raise", "minus", "plus", "allin"):
            buttons[key].enabled = not game.finished and not game.animating
        buttons["raise"].enabled = buttons["raise"].enabled and game.max_raise > 0
        buttons["minus"].enabled = buttons["minus"].enabled and game.raise_amount > 10
        buttons["plus"].enabled = buttons["plus"].enabled and game.raise_amount < game.max_raise
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
