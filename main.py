import pygame

from card import Card
from deck import Deck


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

CARD_WIDTH = 66
CARD_HEIGHT = 96
CARD_GAP = 6

TABLE_COLOR = (30, 120, 70)
CARD_COLOR = (250, 250, 245)
CARD_BORDER_COLOR = (30, 30, 30)
SHADOW_COLOR = (20, 80, 45)
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
RED = (200, 35, 35)


def create_font(size: int, bold: bool = False) -> pygame.font.Font:
    """日本語を表示できるフォントを作る。"""
    font_names = (
        "meiryo",
        "yugothic",
        "msgothic",
    )

    for font_name in font_names:
        font_path = pygame.font.match_font(font_name)

        if font_path is not None:
            font = pygame.font.Font(font_path, size)
            font.set_bold(bold)
            return font

    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font


def create_hands() -> list[list[Card]]:
    """トランプを作り、4人に配る。"""
    deck = Deck()
    deck.shuffle()

    hands = deck.deal(number_of_players=4)

    player_names = ("あなた", "CPU1", "CPU2", "CPU3")

    print("===== カード配布結果 =====")

    for player_name, hand in zip(player_names, hands):
        cards_text = " ".join(str(card) for card in hand)

        print(f"\n{player_name}：{len(hand)}枚")
        print(cards_text)

    return hands


def draw_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    """文字を指定した位置の中央に表示する。"""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=center)
    screen.blit(text_surface, text_rect)


def draw_card(
    screen: pygame.Surface,
    card: Card,
    x: int,
    y: int,
    card_font: pygame.font.Font,
) -> None:
    """カード1枚を描画する。"""
    shadow_rect = pygame.Rect(
        x + 4,
        y + 5,
        CARD_WIDTH,
        CARD_HEIGHT,
    )

    card_rect = pygame.Rect(
        x,
        y,
        CARD_WIDTH,
        CARD_HEIGHT,
    )

    pygame.draw.rect(
        screen,
        SHADOW_COLOR,
        shadow_rect,
        border_radius=7,
    )

    pygame.draw.rect(
        screen,
        CARD_COLOR,
        card_rect,
        border_radius=7,
    )

    pygame.draw.rect(
        screen,
        CARD_BORDER_COLOR,
        card_rect,
        width=2,
        border_radius=7,
    )

    if card.suit in ("♥", "♦"):
        text_color = RED
    else:
        text_color = BLACK

    card_text = card_font.render(
        str(card),
        True,
        text_color,
    )

    card_text_rect = card_text.get_rect(
        center=card_rect.center
    )

    screen.blit(card_text, card_text_rect)


def draw_player_hand(
    screen: pygame.Surface,
    hand: list[Card],
    card_font: pygame.font.Font,
) -> None:
    """画面下部にプレイヤーの手札を並べる。"""
    number_of_cards = len(hand)

    total_width = (
        number_of_cards * CARD_WIDTH
        + (number_of_cards - 1) * CARD_GAP
    )

    start_x = (WINDOW_WIDTH - total_width) // 2
    card_y = WINDOW_HEIGHT - CARD_HEIGHT - 30

    for index, card in enumerate(hand):
        card_x = start_x + index * (CARD_WIDTH + CARD_GAP)

        draw_card(
            screen,
            card,
            card_x,
            card_y,
            card_font,
        )


def draw_game(
    screen: pygame.Surface,
    hands: list[list[Card]],
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    card_font: pygame.font.Font,
) -> None:
    """ゲーム画面全体を描く。"""
    screen.fill(TABLE_COLOR)

    draw_text(
        screen,
        "大富豪ゲーム",
        title_font,
        WHITE,
        (WINDOW_WIDTH // 2, 40),
    )

    draw_text(
        screen,
        f"CPU1：残り{len(hands[1])}枚",
        info_font,
        WHITE,
        (WINDOW_WIDTH // 2, 100),
    )

    draw_text(
        screen,
        f"CPU2：残り{len(hands[2])}枚",
        info_font,
        WHITE,
        (130, WINDOW_HEIGHT // 2),
    )

    draw_text(
        screen,
        f"CPU3：残り{len(hands[3])}枚",
        info_font,
        WHITE,
        (WINDOW_WIDTH - 130, WINDOW_HEIGHT // 2),
    )

    draw_text(
        screen,
        "場：まだカードはありません",
        info_font,
        WHITE,
        (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2),
    )

    draw_text(
        screen,
        f"あなた：残り{len(hands[0])}枚",
        info_font,
        WHITE,
        (WINDOW_WIDTH // 2, 545),
    )

    draw_player_hand(
        screen,
        hands[0],
        card_font,
    )


def main() -> None:
    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )
    pygame.display.set_caption("大富豪ゲーム")

    title_font = create_font(34, bold=True)
    info_font = create_font(23, bold=True)
    card_font = create_font(25, bold=True)

    hands = create_hands()

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        draw_game(
            screen,
            hands,
            title_font,
            info_font,
            card_font,
        )

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()