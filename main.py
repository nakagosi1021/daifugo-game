from dataclasses import dataclass

import pygame

from card import Card
from deck import Deck


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60
CPU_TURN_DELAY_MS = 850
EIGHT_CUT_DISPLAY_MS = 2000

CARD_WIDTH = 66
CARD_HEIGHT = 96
CARD_GAP = 6
SELECTED_RAISE = 25

TABLE_COLOR = (30, 120, 70)
DARK_TABLE_COLOR = (18, 82, 48)
PANEL_COLOR = (22, 95, 56)
CARD_COLOR = (250, 250, 245)
CARD_BORDER_COLOR = (30, 30, 30)
SELECTED_BORDER_COLOR = (255, 210, 40)
SHADOW_COLOR = (20, 80, 45)

BUTTON_COLOR = (235, 235, 235)
BUTTON_HOVER_COLOR = (255, 255, 255)
BUTTON_DISABLED_COLOR = (145, 145, 145)
BUTTON_BORDER_COLOR = (35, 35, 35)

WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
RED = (200, 35, 35)
YELLOW = (255, 225, 80)
LIGHT_BLUE = (170, 220, 255)

PLAYER_NAMES = ("あなた", "CPU1", "CPU2", "CPU3")
RANK_TITLES = ("大富豪", "富豪", "貧民", "大貧民")

PLAY_BUTTON_RECT = pygame.Rect(380, 455, 110, 48)
PASS_BUTTON_RECT = pygame.Rect(510, 455, 110, 48)
START_BUTTON_RECT = pygame.Rect(365, 485, 270, 58)
QUIT_BUTTON_RECT = pygame.Rect(365, 558, 270, 52)
REPLAY_BUTTON_RECT = pygame.Rect(350, 525, 300, 58)
TITLE_BUTTON_RECT = pygame.Rect(350, 595, 300, 48)


@dataclass
class GameState:
    hands: list[list[Card]]
    selected_indices: set[int]
    table_cards: list[Card]
    passed_players: set[int]
    rankings: list[int]
    current_player: int
    last_played_player: int | None
    first_turn: bool
    game_over: bool
    message: str
    turn_started_at: int
    pending_eight_cut_player: int | None
    eight_cut_display_started_at: int | None


def create_font(size: int, bold: bool = False) -> pygame.font.Font:
    font_names = ("meiryo", "yugothic", "msgothic")
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
    deck = Deck()
    deck.shuffle()
    hands = deck.deal(number_of_players=4)
    print("===== カード配布結果 =====")
    for player_name, hand in zip(PLAYER_NAMES, hands):
        cards_text = " ".join(str(card) for card in hand)
        print(f"\n{player_name}：{len(hand)}枚")
        print(cards_text)
    return hands


def find_start_player(hands: list[list[Card]]) -> int:
    for player_index, hand in enumerate(hands):
        for card in hand:
            if card.suit == "♦" and card.rank == "3":
                return player_index
    raise RuntimeError("♦3を持つプレイヤーが見つかりません。")


def create_new_game() -> GameState:
    hands = create_hands()
    current_player = find_start_player(hands)
    return GameState(
        hands=hands,
        selected_indices=set(),
        table_cards=[],
        passed_players=set(),
        rankings=[],
        current_player=current_player,
        last_played_player=None,
        first_turn=True,
        game_over=False,
        message=(
            f"{PLAYER_NAMES[current_player]}が♦3を持っています。"
            "ここから開始します"
        ),
        turn_started_at=pygame.time.get_ticks(),
        pending_eight_cut_player=None,
        eight_cut_display_started_at=None,
    )


def get_active_players(hands: list[list[Card]]) -> list[int]:
    return [i for i, hand in enumerate(hands) if hand]


def get_next_player(
    current_player: int,
    hands: list[list[Card]],
    passed_players: set[int],
) -> int | None:
    number_of_players = len(hands)
    for offset in range(1, number_of_players):
        candidate = (current_player + offset) % number_of_players
        if hands[candidate] and candidate not in passed_players:
            return candidate
    return None


def register_finish(
    player_index: int,
    hands: list[list[Card]],
    rankings: list[int],
) -> None:
    if not hands[player_index] and player_index not in rankings:
        rankings.append(player_index)


def complete_ranking_if_game_over(
    hands: list[list[Card]],
    rankings: list[int],
) -> bool:
    active_players = get_active_players(hands)
    if len(active_players) > 1:
        return False
    if active_players and active_players[0] not in rankings:
        rankings.append(active_players[0])
    return True


def draw_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=center)
    screen.blit(text_surface, text_rect)


def draw_panel(screen: pygame.Surface, rect: pygame.Rect) -> None:
    shadow_rect = rect.move(5, 6)
    pygame.draw.rect(screen, SHADOW_COLOR, shadow_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_COLOR, rect, border_radius=14)
    pygame.draw.rect(screen, WHITE, rect, width=2, border_radius=14)


def get_player_card_rects(
    hand: list[Card],
    selected_indices: set[int],
) -> list[pygame.Rect]:
    if not hand:
        return []
    number_of_cards = len(hand)
    total_width = number_of_cards * CARD_WIDTH + (number_of_cards - 1) * CARD_GAP
    start_x = (WINDOW_WIDTH - total_width) // 2
    base_y = WINDOW_HEIGHT - CARD_HEIGHT - 30
    card_rects: list[pygame.Rect] = []
    for index in range(number_of_cards):
        card_x = start_x + index * (CARD_WIDTH + CARD_GAP)
        card_y = base_y - SELECTED_RAISE if index in selected_indices else base_y
        card_rects.append(pygame.Rect(card_x, card_y, CARD_WIDTH, CARD_HEIGHT))
    return card_rects


def draw_card(
    screen: pygame.Surface,
    card: Card,
    card_rect: pygame.Rect,
    card_font: pygame.font.Font,
    selected: bool = False,
) -> None:
    shadow_rect = card_rect.move(4, 5)
    pygame.draw.rect(screen, SHADOW_COLOR, shadow_rect, border_radius=7)
    pygame.draw.rect(screen, CARD_COLOR, card_rect, border_radius=7)
    border_color = SELECTED_BORDER_COLOR if selected else CARD_BORDER_COLOR
    border_width = 4 if selected else 2
    pygame.draw.rect(
        screen, border_color, card_rect, width=border_width, border_radius=7
    )
    text_color = RED if card.suit in ("♥", "♦") else BLACK
    card_text = card_font.render(str(card), True, text_color)
    card_text_rect = card_text.get_rect(center=card_rect.center)
    screen.blit(card_text, card_text_rect)


def draw_player_hand(
    screen: pygame.Surface,
    hand: list[Card],
    selected_indices: set[int],
    card_font: pygame.font.Font,
) -> None:
    card_rects = get_player_card_rects(hand, selected_indices)
    for index, card in enumerate(hand):
        draw_card(
            screen=screen,
            card=card,
            card_rect=card_rects[index],
            card_font=card_font,
            selected=index in selected_indices,
        )


def draw_table_cards(
    screen: pygame.Surface,
    table_cards: list[Card],
    card_font: pygame.font.Font,
) -> None:
    if not table_cards:
        return
    total_width = len(table_cards) * CARD_WIDTH + (len(table_cards) - 1) * CARD_GAP
    start_x = (WINDOW_WIDTH - total_width) // 2
    card_y = 270
    for index, card in enumerate(table_cards):
        card_x = start_x + index * (CARD_WIDTH + CARD_GAP)
        card_rect = pygame.Rect(card_x, card_y, CARD_WIDTH, CARD_HEIGHT)
        draw_card(screen, card, card_rect, card_font)


def draw_button(
    screen: pygame.Surface,
    button_rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    mouse_position: tuple[int, int],
    enabled: bool = True,
) -> None:
    if not enabled:
        background_color = BUTTON_DISABLED_COLOR
    elif button_rect.collidepoint(mouse_position):
        background_color = BUTTON_HOVER_COLOR
    else:
        background_color = BUTTON_COLOR
    pygame.draw.rect(screen, background_color, button_rect, border_radius=8)
    pygame.draw.rect(
        screen,
        BUTTON_BORDER_COLOR,
        button_rect,
        width=2,
        border_radius=8,
    )
    draw_text(screen, text, font, BLACK, button_rect.center)


def handle_card_click(
    mouse_position: tuple[int, int],
    hand: list[Card],
    selected_indices: set[int],
) -> None:
    card_rects = get_player_card_rects(hand, selected_indices)
    for index in range(len(card_rects) - 1, -1, -1):
        if card_rects[index].collidepoint(mouse_position):
            if index in selected_indices:
                selected_indices.remove(index)
            else:
                selected_indices.add(index)
            break


def get_selected_cards(
    hand: list[Card],
    selected_indices: set[int],
) -> list[Card]:
    return [hand[index] for index in sorted(selected_indices)]


def validate_play(
    selected_cards: list[Card],
    table_cards: list[Card],
    first_turn: bool,
) -> tuple[bool, str]:
    if not selected_cards:
        return False, "カードを選択してください"
    first_rank = selected_cards[0].rank
    if any(card.rank != first_rank for card in selected_cards):
        return False, "同じ数字のカードだけを選択してください"
    if first_turn:
        contains_diamond_three = any(
            card.suit == "♦" and card.rank == "3" for card in selected_cards
        )
        if not contains_diamond_three:
            return False, "最初は♦3を含むカードを出してください"
    if not table_cards:
        return True, ""
    if len(selected_cards) != len(table_cards):
        return False, f"場と同じ{len(table_cards)}枚を出してください"
    if selected_cards[0].strength <= table_cards[0].strength:
        return False, "場より強いカードを出してください"
    return True, ""


def choose_cpu_cards(
    hand: list[Card],
    table_cards: list[Card],
    first_turn: bool,
) -> list[Card]:
    if first_turn:
        for card in hand:
            if card.suit == "♦" and card.rank == "3":
                return [card]
        return []
    groups: dict[str, list[Card]] = {}
    for card in hand:
        groups.setdefault(card.rank, []).append(card)
    if not table_cards:
        return [min(hand, key=lambda card: card.strength)]
    required_count = len(table_cards)
    required_strength = table_cards[0].strength
    candidate_groups: list[list[Card]] = []
    for cards in groups.values():
        if len(cards) >= required_count and cards[0].strength > required_strength:
            candidate_groups.append(cards)
    if not candidate_groups:
        return []
    candidate_groups.sort(key=lambda cards: cards[0].strength)
    return candidate_groups[0][:required_count]


def play_cards(
    player_index: int,
    cards_to_play: list[Card],
    hands: list[list[Card]],
    table_cards: list[Card],
    passed_players: set[int],
    rankings: list[int],
) -> bool:
    for card in cards_to_play:
        hands[player_index].remove(card)
    table_cards[:] = cards_to_play
    passed_players.discard(player_index)
    register_finish(player_index, hands, rankings)
    return complete_ranking_if_game_over(hands, rankings)


def is_eight_cut(cards: list[Card]) -> bool:
    """出した組が8なら8切りを成立させる。"""
    return bool(cards) and all(card.rank == "8" for card in cards)


def start_eight_cut_wait(game: GameState, player_index: int) -> None:
    """8を描画した後、一定時間表示してから場を流す準備をする。"""
    game.pending_eight_cut_player = player_index

    # ここではまだ時間を開始しない。
    # pygame.display.flip()で8が実際に描画された後に開始する。
    game.eight_cut_display_started_at = None

    played_text = " ".join(str(card) for card in game.table_cards)
    game.message = (
        f"{PLAYER_NAMES[player_index]}は {played_text} を出しました　"
        "8切り！"
    )


def apply_eight_cut(game: GameState, player_index: int) -> None:
    """表示時間の経過後に場を流し、次の場を始める。"""
    game.table_cards.clear()
    game.passed_players.clear()
    game.last_played_player = None
    game.pending_eight_cut_player = None
    game.eight_cut_display_started_at = None

    if game.game_over:
        game.current_player = -1
        game.message = "8切り！ゲーム終了。順位が決まりました"
        return

    if game.hands[player_index]:
        next_player = player_index
    else:
        next_player = get_next_player(
            player_index,
            game.hands,
            set(),
        )

    if next_player is None:
        raise RuntimeError("8切り後のプレイヤーを決められませんでした。")

    game.current_player = next_player
    game.message = (
        "8切り！場が流れました。"
        f"{PLAYER_NAMES[next_player]}から再開します"
    )
    game.turn_started_at = pygame.time.get_ticks()


def process_pass(
    player_index: int,
    hands: list[list[Card]],
    table_cards: list[Card],
    passed_players: set[int],
    last_played_player: int | None,
) -> tuple[int | None, bool]:
    passed_players.add(player_index)
    active_players = get_active_players(hands)
    challengers = [
        active_player
        for active_player in active_players
        if active_player != last_played_player
    ]
    all_other_players_passed = (
        last_played_player is not None
        and all(challenger in passed_players for challenger in challengers)
    )
    if all_other_players_passed:
        table_cards.clear()
        passed_players.clear()
        if last_played_player is not None and hands[last_played_player]:
            next_player = last_played_player
        elif last_played_player is not None:
            next_player = get_next_player(last_played_player, hands, set())
        else:
            next_player = None
        return next_player, True
    next_player = get_next_player(player_index, hands, passed_players)
    return next_player, False


def draw_title_screen(
    screen: pygame.Surface,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
    card_font: pygame.font.Font,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    mouse_position = pygame.mouse.get_pos()
    draw_text(screen, "大富豪", title_font, WHITE, (WINDOW_WIDTH // 2, 92))
    draw_text(
        screen,
        "あなた1人 vs CPU3人",
        info_font,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 145),
    )
    sample_cards = (Card("♠", "3"), Card("♥", "8"), Card("♦", "2"))
    sample_x = WINDOW_WIDTH // 2 - 117
    for index, card in enumerate(sample_cards):
        rect = pygame.Rect(sample_x + index * 84, 190, CARD_WIDTH, CARD_HEIGHT)
        draw_card(screen, card, rect, card_font)
    panel_rect = pygame.Rect(220, 310, 560, 155)
    draw_panel(screen, panel_rect)
    rules = (
        "♦3を持つ人からスタート",
        "3が最弱、2が最強／同じ数字は複数枚出せます",
        "全員がパスすると場が流れます",
        "ローカルルール：8を出すと場が流れます",
    )
    for index, rule in enumerate(rules):
        draw_text(
            screen,
            rule,
            small_font,
            WHITE,
            (WINDOW_WIDTH // 2, 335 + index * 34),
        )
    draw_button(
        screen,
        START_BUTTON_RECT,
        "ゲーム開始",
        button_font,
        mouse_position,
    )
    draw_button(
        screen,
        QUIT_BUTTON_RECT,
        "終了",
        button_font,
        mouse_position,
    )
    draw_text(
        screen,
        "Enterキーでも開始できます",
        small_font,
        WHITE,
        (WINDOW_WIDTH // 2, 655),
    )


def draw_result_screen(
    screen: pygame.Surface,
    game: GameState,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    mouse_position = pygame.mouse.get_pos()
    draw_text(screen, "ゲーム終了", title_font, YELLOW, (WINDOW_WIDTH // 2, 75))
    if game.rankings and game.rankings[0] == 0:
        result_message = "優勝です！"
    else:
        human_place = game.rankings.index(0) + 1
        result_message = f"あなたは{human_place}位でした"
    draw_text(
        screen,
        result_message,
        info_font,
        WHITE,
        (WINDOW_WIDTH // 2, 125),
    )
    panel_rect = pygame.Rect(260, 165, 480, 315)
    draw_panel(screen, panel_rect)
    for place, player_index in enumerate(game.rankings, start=1):
        rank_title = RANK_TITLES[place - 1]
        color = YELLOW if player_index == 0 else WHITE
        draw_text(
            screen,
            f"{place}位　{rank_title}　{PLAYER_NAMES[player_index]}",
            info_font,
            color,
            (WINDOW_WIDTH // 2, 205 + (place - 1) * 68),
        )
    draw_button(
        screen,
        REPLAY_BUTTON_RECT,
        "もう一度遊ぶ",
        button_font,
        mouse_position,
    )
    draw_button(
        screen,
        TITLE_BUTTON_RECT,
        "タイトルへ戻る",
        button_font,
        mouse_position,
    )
    draw_text(
        screen,
        "Enter：もう一度　　Esc：タイトル",
        small_font,
        WHITE,
        (WINDOW_WIDTH // 2, 672),
    )


def draw_game(
    screen: pygame.Surface,
    hands: list[list[Card]],
    table_cards: list[Card],
    selected_indices: set[int],
    passed_players: set[int],
    current_player: int,
    message: str,
    rankings: list[int],
    game_over: bool,
    eight_cut_pending: bool,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
    card_font: pygame.font.Font,
) -> None:
    screen.fill(TABLE_COLOR)
    mouse_position = pygame.mouse.get_pos()
    draw_text(screen, "大富豪ゲーム", title_font, WHITE, (WINDOW_WIDTH // 2, 36))
    if eight_cut_pending:
        turn_text = "8切り発動！"
        turn_color = YELLOW
    elif game_over:
        turn_text = "ゲーム終了"
        turn_color = LIGHT_BLUE
    else:
        turn_text = f"現在の番：{PLAYER_NAMES[current_player]}"
        turn_color = LIGHT_BLUE

    draw_text(
        screen,
        turn_text,
        info_font,
        turn_color,
        (WINDOW_WIDTH // 2, 72),
    )
    cpu_positions = (
        (WINDOW_WIDTH // 2, 110),
        (130, WINDOW_HEIGHT // 2),
        (WINDOW_WIDTH - 130, WINDOW_HEIGHT // 2),
    )
    for player_index, position in zip((1, 2, 3), cpu_positions):
        if not hands[player_index]:
            status = "あがり"
        elif player_index in passed_players:
            status = "パス中"
        else:
            status = f"残り{len(hands[player_index])}枚"
        draw_text(
            screen,
            f"{PLAYER_NAMES[player_index]}：{status}",
            info_font,
            WHITE,
            position,
        )
    if table_cards:
        table_text = f"場：{len(table_cards)}枚組・{table_cards[0].rank}"
    else:
        table_text = "場：まだカードはありません"
    draw_text(screen, table_text, info_font, WHITE, (WINDOW_WIDTH // 2, 225))
    draw_table_cards(screen, table_cards, card_font)
    draw_text(screen, message, small_font, YELLOW, (WINDOW_WIDTH // 2, 405))
    human_turn = (
        not game_over
        and not eight_cut_pending
        and current_player == 0
        and bool(hands[0])
    )
    draw_button(
        screen,
        PLAY_BUTTON_RECT,
        "出す",
        button_font,
        mouse_position,
        enabled=human_turn and bool(selected_indices),
    )
    draw_button(
        screen,
        PASS_BUTTON_RECT,
        "パス",
        button_font,
        mouse_position,
        enabled=human_turn and bool(table_cards),
    )
    human_status = f"残り{len(hands[0])}枚" if hands[0] else "あがり"
    draw_text(
        screen,
        f"あなた：{human_status}",
        info_font,
        WHITE,
        (WINDOW_WIDTH // 2, 525),
    )
    draw_text(
        screen,
        f"選択中：{len(selected_indices)}枚",
        small_font,
        SELECTED_BORDER_COLOR,
        (WINDOW_WIDTH // 2, 552),
    )
    draw_player_hand(screen, hands[0], selected_indices, card_font)
    for place, player_index in enumerate(rankings, start=1):
        draw_text(
            screen,
            f"{place}位：{PLAYER_NAMES[player_index]}",
            small_font,
            WHITE,
            (855, 70 + place * 26),
        )


def move_to_next_player(game: GameState, from_player: int) -> None:
    next_player = get_next_player(from_player, game.hands, game.passed_players)
    if next_player is None:
        raise RuntimeError("次のプレイヤーを決められませんでした。")
    game.current_player = next_player
    game.turn_started_at = pygame.time.get_ticks()


def handle_human_play(game: GameState) -> None:
    selected_cards = get_selected_cards(game.hands[0], game.selected_indices)
    is_valid, error_message = validate_play(
        selected_cards,
        game.table_cards,
        game.first_turn,
    )
    if not is_valid:
        game.message = error_message
        return
    game.game_over = play_cards(
        player_index=0,
        cards_to_play=selected_cards,
        hands=game.hands,
        table_cards=game.table_cards,
        passed_players=game.passed_players,
        rankings=game.rankings,
    )
    game.selected_indices.clear()
    game.last_played_player = 0
    game.first_turn = False
    played_text = " ".join(str(card) for card in selected_cards)
    game.message = f"あなたは {played_text} を出しました"
    if is_eight_cut(selected_cards):
        start_eight_cut_wait(game, 0)
    elif game.game_over:
        game.current_player = -1
        game.message = "ゲーム終了！順位が決まりました"
    else:
        move_to_next_player(game, 0)


def handle_human_pass(game: GameState) -> None:
    if not game.table_cards:
        game.message = "場が空のときはパスできません"
        return
    game.selected_indices.clear()
    next_player, table_cleared = process_pass(
        player_index=0,
        hands=game.hands,
        table_cards=game.table_cards,
        passed_players=game.passed_players,
        last_played_player=game.last_played_player,
    )
    if next_player is None:
        raise RuntimeError("パス後のプレイヤーを決められませんでした。")
    game.current_player = next_player
    game.message = "場が流れました" if table_cleared else "あなたはパスしました"
    game.turn_started_at = pygame.time.get_ticks()


def process_cpu_turn(game: GameState) -> None:
    cpu_player = game.current_player
    cpu_cards = choose_cpu_cards(
        hand=game.hands[cpu_player],
        table_cards=game.table_cards,
        first_turn=game.first_turn,
    )
    if cpu_cards:
        game.game_over = play_cards(
            player_index=cpu_player,
            cards_to_play=cpu_cards,
            hands=game.hands,
            table_cards=game.table_cards,
            passed_players=game.passed_players,
            rankings=game.rankings,
        )
        game.last_played_player = cpu_player
        game.first_turn = False
        played_text = " ".join(str(card) for card in cpu_cards)
        game.message = f"{PLAYER_NAMES[cpu_player]}は {played_text} を出しました"
        if is_eight_cut(cpu_cards):
            start_eight_cut_wait(game, cpu_player)
        elif game.game_over:
            game.current_player = -1
            game.message = "ゲーム終了！順位が決まりました"
        else:
            move_to_next_player(game, cpu_player)
    else:
        next_player, table_cleared = process_pass(
            player_index=cpu_player,
            hands=game.hands,
            table_cards=game.table_cards,
            passed_players=game.passed_players,
            last_played_player=game.last_played_player,
        )
        if next_player is None:
            raise RuntimeError("CPUのパス後に次のプレイヤーを決められませんでした。")
        game.current_player = next_player
        if table_cleared:
            game.message = f"{PLAYER_NAMES[cpu_player]}のパスで場が流れました"
        else:
            game.message = f"{PLAYER_NAMES[cpu_player]}はパスしました"
        game.turn_started_at = pygame.time.get_ticks()


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("大富豪ゲーム")

    title_font = create_font(42, bold=True)
    info_font = create_font(20, bold=True)
    small_font = create_font(17, bold=True)
    button_font = create_font(21, bold=True)
    card_font = create_font(25, bold=True)

    screen_mode = "title"
    game: GameState | None = None

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif screen_mode == "title":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if START_BUTTON_RECT.collidepoint(event.pos):
                        game = create_new_game()
                        screen_mode = "game"
                    elif QUIT_BUTTON_RECT.collidepoint(event.pos):
                        running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game = create_new_game()
                        screen_mode = "game"
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            elif screen_mode == "result":
                if game is None:
                    raise RuntimeError("ゲーム結果がありません。")
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if REPLAY_BUTTON_RECT.collidepoint(event.pos):
                        game = create_new_game()
                        screen_mode = "game"
                    elif TITLE_BUTTON_RECT.collidepoint(event.pos):
                        game = None
                        screen_mode = "title"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game = create_new_game()
                        screen_mode = "game"
                    elif event.key in (pygame.K_ESCAPE, pygame.K_t):
                        game = None
                        screen_mode = "title"

            elif screen_mode == "game":
                if game is None:
                    raise RuntimeError("ゲーム状態がありません。")
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and not game.game_over
                    and game.current_player == 0
                    and game.pending_eight_cut_player is None
                ):
                    if PLAY_BUTTON_RECT.collidepoint(event.pos):
                        handle_human_play(game)
                    elif PASS_BUTTON_RECT.collidepoint(event.pos):
                        handle_human_pass(game)
                    else:
                        handle_card_click(
                            event.pos,
                            game.hands[0],
                            game.selected_indices,
                        )
                elif (
                    event.type == pygame.KEYDOWN
                    and not game.game_over
                    and game.current_player == 0
                    and game.pending_eight_cut_player is None
                ):
                    if event.key == pygame.K_ESCAPE:
                        game.selected_indices.clear()
                        game.message = "選択を解除しました"
                    elif event.key == pygame.K_RETURN:
                        handle_human_play(game)
                    elif event.key == pygame.K_p:
                        handle_human_pass(game)

        if screen_mode == "game":
            if game is None:
                raise RuntimeError("ゲーム状態がありません。")
            current_time = pygame.time.get_ticks()

            if game.pending_eight_cut_player is not None:
                # 8が少なくとも1回画面に描画されてから時間を数える。
                if game.eight_cut_display_started_at is not None:
                    eight_cut_wait_finished = (
                        current_time
                        - game.eight_cut_display_started_at
                        >= EIGHT_CUT_DISPLAY_MS
                    )
                    if eight_cut_wait_finished:
                        apply_eight_cut(
                            game,
                            game.pending_eight_cut_player,
                        )
            else:
                cpu_wait_finished = (
                    current_time - game.turn_started_at
                    >= CPU_TURN_DELAY_MS
                )
                if (
                    not game.game_over
                    and game.current_player != 0
                    and cpu_wait_finished
                ):
                    process_cpu_turn(game)

            if (
                game.game_over
                and game.pending_eight_cut_player is None
            ):
                screen_mode = "result"

        if screen_mode == "title":
            draw_title_screen(
                screen,
                title_font,
                info_font,
                small_font,
                button_font,
                card_font,
            )
        elif screen_mode == "game":
            if game is None:
                raise RuntimeError("ゲーム状態がありません。")
            draw_game(
                screen=screen,
                hands=game.hands,
                table_cards=game.table_cards,
                selected_indices=game.selected_indices,
                passed_players=game.passed_players,
                current_player=game.current_player,
                message=game.message,
                rankings=game.rankings,
                game_over=game.game_over,
                eight_cut_pending=(
                    game.pending_eight_cut_player is not None
                ),
                title_font=title_font,
                info_font=info_font,
                small_font=small_font,
                button_font=button_font,
                card_font=card_font,
            )
        else:
            if game is None:
                raise RuntimeError("ゲーム結果がありません。")
            draw_result_screen(
                screen,
                game,
                title_font,
                info_font,
                small_font,
                button_font,
            )

        pygame.display.flip()

        # 8のカードが実際に画面へ表示された後で、
        # 2秒間の表示タイマーを開始する。
        if (
            screen_mode == "game"
            and game is not None
            and game.pending_eight_cut_player is not None
            and game.eight_cut_display_started_at is None
        ):
            game.eight_cut_display_started_at = pygame.time.get_ticks()

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
