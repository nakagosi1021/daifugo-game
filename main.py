import pygame

from card import Card
from deck import Deck


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

CARD_WIDTH = 66
CARD_HEIGHT = 96
CARD_GAP = 6
SELECTED_RAISE = 25

TABLE_COLOR = (30, 120, 70)
CARD_COLOR = (250, 250, 245)
CARD_BORDER_COLOR = (30, 30, 30)
SELECTED_BORDER_COLOR = (255, 210, 40)
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
    """トランプを作成し、4人に配る。"""
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


def get_player_card_rects(
    hand: list[Card],
    selected_indices: set[int],
) -> list[pygame.Rect]:
    """プレイヤーの各カードの表示位置を返す。"""
    number_of_cards = len(hand)

    total_width = (
        number_of_cards * CARD_WIDTH
        + (number_of_cards - 1) * CARD_GAP
    )

    start_x = (WINDOW_WIDTH - total_width) // 2
    base_y = WINDOW_HEIGHT - CARD_HEIGHT - 30

    card_rects: list[pygame.Rect] = []

    for index in range(number_of_cards):
        card_x = start_x + index * (CARD_WIDTH + CARD_GAP)

        if index in selected_indices:
            card_y = base_y - SELECTED_RAISE
        else:
            card_y = base_y

        card_rects.append(
            pygame.Rect(
                card_x,
                card_y,
                CARD_WIDTH,
                CARD_HEIGHT,
            )
        )

    return card_rects


def draw_card(
    screen: pygame.Surface,
    card: Card,
    card_rect: pygame.Rect,
    card_font: pygame.font.Font,
    selected: bool,
) -> None:
    """カード1枚を描画する。"""
    shadow_rect = card_rect.move(4, 5)

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

    if selected:
        border_color = SELECTED_BORDER_COLOR
        border_width = 4
    else:
        border_color = CARD_BORDER_COLOR
        border_width = 2

    pygame.draw.rect(
        screen,
        border_color,
        card_rect,
        width=border_width,
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
    selected_indices: set[int],
    card_font: pygame.font.Font,
) -> None:
    """画面下部にプレイヤーの手札を並べる。"""
    card_rects = get_player_card_rects(
        hand,
        selected_indices,
    )

    for index, card in enumerate(hand):
        draw_card(
            screen=screen,
            card=card,
            card_rect=card_rects[index],
            card_font=card_font,
            selected=index in selected_indices,
        )


def handle_card_click(
    mouse_position: tuple[int, int],
    hand: list[Card],
    selected_indices: set[int],
) -> None:
    """クリックされたカードの選択状態を切り替える。"""
    card_rects = get_player_card_rects(
        hand,
        selected_indices,
    )

    # 右側のカードから確認する
    for index in range(len(card_rects) - 1, -1, -1):
        if card_rects[index].collidepoint(mouse_position):
            if index in selected_indices:
                selected_indices.remove(index)
            else:
                selected_indices.add(index)

            break


def draw_game(
    screen: pygame.Surface,
    hands: list[list[Card]],
    selected_indices: set[int],
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
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
        (WINDOW_WIDTH // 2, 515),
    )

    draw_text(
        screen,
        f"選択中：{len(selected_indices)}枚",
        small_font,
        SELECTED_BORDER_COLOR,
        (WINDOW_WIDTH // 2, 545),
    )

    draw_player_hand(
        screen,
        hands[0],
        selected_indices,
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
    small_font = create_font(18, bold=True)
    card_font = create_font(25, bold=True)

    hands = create_hands()

    # 選択されているカード番号を保存する
    selected_indices: set[int] = set()

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                handle_card_click(
                    mouse_position=event.pos,
                    hand=hands[0],
                    selected_indices=selected_indices,
                )

            elif event.type == pygame.KEYDOWN:
                # Escキーで選択をすべて解除する
                if event.key == pygame.K_ESCAPE:
                    selected_indices.clear()

        draw_game(
            screen,
            hands,
            selected_indices,
            title_font,
            info_font,
            small_font,
            card_font,
        )

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()