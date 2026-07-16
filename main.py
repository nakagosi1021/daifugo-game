from __future__ import annotations

import pygame

from card import Card
from game_engine import (
    GameSession,
    GameState,
    PLAYER_NAMES,
    RANK_TITLES,
    confirm_pending_selection,
    create_game,
    pass_turn,
    play_cards,
    process_cpu_turn,
    resolve_pending_display,
    state_status_lines,
    table_description,
)
from rules import RULE_INFOS, RuleSettings

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 760
FPS = 60
CPU_TURN_DELAY_MS = 850

CARD_WIDTH = 64
CARD_HEIGHT = 94
SELECTED_RAISE = 24

TABLE_COLOR = (31, 116, 72)
DARK_TABLE_COLOR = (16, 72, 47)
PANEL_COLOR = (24, 91, 59)
CARD_COLOR = (250, 249, 244)
CARD_BORDER = (30, 30, 30)
SHADOW_COLOR = (13, 65, 40)
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
RED = (195, 36, 42)
YELLOW = (255, 222, 70)
LIGHT_BLUE = (164, 221, 255)
GREEN = (92, 220, 126)
GRAY = (150, 150, 150)
PURPLE = (125, 61, 170)
BUTTON_COLOR = (238, 238, 238)
BUTTON_HOVER = (255, 255, 255)
BUTTON_DISABLED = (145, 145, 145)

TITLE_START_RECT = pygame.Rect(385, 480, 330, 62)
TITLE_QUIT_RECT = pygame.Rect(385, 560, 330, 54)
RULE_START_RECT = pygame.Rect(770, 665, 260, 55)
RULE_BACK_RECT = pygame.Rect(70, 665, 210, 55)
PRESET_SIMPLE_RECT = pygame.Rect(340, 665, 125, 55)
PRESET_STANDARD_RECT = pygame.Rect(480, 665, 140, 55)
PRESET_PARTY_RECT = pygame.Rect(635, 665, 120, 55)
PLAY_RECT = pygame.Rect(415, 500, 125, 48)
PASS_RECT = pygame.Rect(560, 500, 125, 48)
RESULT_NEXT_RECT = pygame.Rect(365, 560, 370, 58)
RESULT_RESET_RECT = pygame.Rect(365, 630, 370, 50)


def create_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ("meiryo", "yugothic", "msgothic"):
        path = pygame.font.match_font(name)
        if path:
            font = pygame.font.Font(path, size)
            font.set_bold(bold)
            return font
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font


def draw_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))


def draw_panel(screen: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(screen, SHADOW_COLOR, rect.move(5, 6), border_radius=14)
    pygame.draw.rect(screen, PANEL_COLOR, rect, border_radius=14)
    pygame.draw.rect(screen, WHITE, rect, width=2, border_radius=14)


def draw_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    enabled: bool = True,
) -> None:
    mouse = pygame.mouse.get_pos()
    if not enabled:
        color = BUTTON_DISABLED
    elif rect.collidepoint(mouse):
        color = BUTTON_HOVER
    else:
        color = BUTTON_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=9)
    pygame.draw.rect(screen, BLACK, rect, width=2, border_radius=9)
    draw_text(screen, label, font, BLACK, rect.center)


def card_rects(hand: list[Card], selected: set[int]) -> list[pygame.Rect]:
    if not hand:
        return []
    available_width = WINDOW_WIDTH - 44
    if len(hand) == 1:
        step = 0.0
        total = CARD_WIDTH
    else:
        normal_step = CARD_WIDTH + 5
        normal_total = CARD_WIDTH + normal_step * (len(hand) - 1)
        step = normal_step if normal_total <= available_width else (
            available_width - CARD_WIDTH
        ) / (len(hand) - 1)
        total = CARD_WIDTH + step * (len(hand) - 1)
    start_x = (WINDOW_WIDTH - total) / 2
    base_y = WINDOW_HEIGHT - CARD_HEIGHT - 22
    result: list[pygame.Rect] = []
    for index in range(len(hand)):
        y = base_y - SELECTED_RAISE if index in selected else base_y
        result.append(pygame.Rect(int(start_x + step * index), int(y), CARD_WIDTH, CARD_HEIGHT))
    return result


def draw_card(
    screen: pygame.Surface,
    card: Card,
    rect: pygame.Rect,
    card_font: pygame.font.Font,
    selected: bool = False,
) -> None:
    pygame.draw.rect(screen, SHADOW_COLOR, rect.move(4, 5), border_radius=7)
    pygame.draw.rect(screen, CARD_COLOR, rect, border_radius=7)
    border = YELLOW if selected else CARD_BORDER
    pygame.draw.rect(screen, border, rect, width=4 if selected else 2, border_radius=7)

    if card.is_joker:
        label = "JK"
        color = PURPLE
    else:
        label = str(card)
        color = RED if card.suit in ("♥", "♦") else BLACK
    draw_text(screen, label, card_font, color, rect.center)


def draw_hand(
    screen: pygame.Surface,
    hand: list[Card],
    selected: set[int],
    card_font: pygame.font.Font,
) -> None:
    rects = card_rects(hand, selected)
    for index, card in enumerate(hand):
        draw_card(screen, card, rects[index], card_font, index in selected)


def draw_table_cards(
    screen: pygame.Surface,
    cards: list[Card],
    card_font: pygame.font.Font,
) -> None:
    if not cards:
        return
    gap = 7
    total = CARD_WIDTH * len(cards) + gap * (len(cards) - 1)
    start_x = (WINDOW_WIDTH - total) // 2
    for index, card in enumerate(cards):
        rect = pygame.Rect(start_x + index * (CARD_WIDTH + gap), 270, CARD_WIDTH, CARD_HEIGHT)
        draw_card(screen, card, rect, card_font)


def clicked_card_index(
    position: tuple[int, int],
    hand: list[Card],
    selected: set[int],
) -> int | None:
    rects = card_rects(hand, selected)
    for index in range(len(rects) - 1, -1, -1):
        if rects[index].collidepoint(position):
            return index
    return None


def draw_title(
    screen: pygame.Surface,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
    card_font: pygame.font.Font,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "大富豪", title_font, WHITE, (WINDOW_WIDTH // 2, 95))
    draw_text(
        screen,
        "好きなローカルルールを選べるCPU対戦ゲーム",
        info_font,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 150),
    )
    samples = (Card("♠", "3"), Card("♥", "8"), Card("JOKER", "JOKER"), Card("♦", "2"))
    start_x = WINDOW_WIDTH // 2 - 155
    for index, card in enumerate(samples):
        draw_card(
            screen,
            card,
            pygame.Rect(start_x + index * 84, 205, CARD_WIDTH, CARD_HEIGHT),
            card_font,
        )
    panel = pygame.Rect(230, 330, 640, 100)
    draw_panel(screen, panel)
    draw_text(
        screen,
        "基本ルールから、8切り・革命・縛り・階段・7渡しなどを自由に設定",
        small_font,
        WHITE,
        (WINDOW_WIDTH // 2, 368),
    )
    draw_text(
        screen,
        "2戦目以降はカード交換や都落ちも使用できます",
        small_font,
        WHITE,
        (WINDOW_WIDTH // 2, 403),
    )
    draw_button(screen, TITLE_START_RECT, "ルールを選んで開始", button_font)
    draw_button(screen, TITLE_QUIT_RECT, "終了", button_font)
    draw_text(screen, "Enter：ルール設定", small_font, WHITE, (WINDOW_WIDTH // 2, 680))


def rule_checkbox_rects() -> dict[str, pygame.Rect]:
    rects: dict[str, pygame.Rect] = {}
    for index, info in enumerate(RULE_INFOS):
        column = 0 if index < 7 else 1
        row = index if column == 0 else index - 7
        x = 70 if column == 0 else 570
        y = 115 + row * 73
        rects[info.key] = pygame.Rect(x, y, 455, 60)
    return rects


def draw_rules_screen(
    screen: pygame.Surface,
    settings: RuleSettings,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "ルール設定", title_font, WHITE, (WINDOW_WIDTH // 2, 48))
    draw_text(
        screen,
        "各項目をクリックしてON／OFFを切り替えてください",
        small_font,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 84),
    )
    rects = rule_checkbox_rects()
    mouse = pygame.mouse.get_pos()
    for info in RULE_INFOS:
        rect = rects[info.key]
        enabled = bool(getattr(settings, info.key))
        background = (31, 112, 72) if enabled else (55, 72, 64)
        if rect.collidepoint(mouse):
            background = (40, 130, 83) if enabled else (66, 86, 76)
        pygame.draw.rect(screen, background, rect, border_radius=10)
        pygame.draw.rect(screen, GREEN if enabled else GRAY, rect, width=2, border_radius=10)
        status_rect = pygame.Rect(rect.x + 12, rect.y + 13, 62, 34)
        pygame.draw.rect(screen, GREEN if enabled else GRAY, status_rect, border_radius=7)
        draw_text(screen, "ON" if enabled else "OFF", small_font, BLACK, status_rect.center)
        label_surface = info_font.render(info.label, True, WHITE)
        screen.blit(label_surface, (rect.x + 88, rect.y + 7))
        description = small_font.render(info.description, True, (220, 230, 225))
        screen.blit(description, (rect.x + 88, rect.y + 34))

    draw_button(screen, RULE_BACK_RECT, "タイトルへ戻る", button_font)
    draw_button(screen, PRESET_SIMPLE_RECT, "基本のみ", small_font)
    draw_button(screen, PRESET_STANDARD_RECT, "標準", small_font)
    draw_button(screen, PRESET_PARTY_RECT, "全部ON", small_font)
    draw_button(screen, RULE_START_RECT, "このルールで開始", button_font)


def draw_game_screen(
    screen: pygame.Surface,
    state: GameState,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
    card_font: pygame.font.Font,
) -> None:
    screen.fill(TABLE_COLOR)
    draw_text(screen, f"大富豪　第{state.session.round_number}戦", title_font, WHITE, (WINDOW_WIDTH // 2, 33))

    if state.pending_display:
        turn_text = "8切り発動！" if state.pending_display.effect == "eight_cut" else "スペード3返し！"
        turn_color = YELLOW
    elif state.pending_selection:
        turn_text = "特殊効果のカードを選択中"
        turn_color = YELLOW
    elif state.game_over:
        turn_text = "ゲーム終了"
        turn_color = YELLOW
    else:
        turn_text = f"現在の番：{PLAYER_NAMES[state.current_player]}"
        turn_color = LIGHT_BLUE
    draw_text(screen, turn_text, info_font, turn_color, (WINDOW_WIDTH // 2, 68))

    statuses = state_status_lines(state)
    draw_text(screen, " / ".join(statuses), small_font, YELLOW if len(statuses) > 1 else WHITE, (165, 68))

    cpu_positions = ((WINDOW_WIDTH // 2, 108), (125, 335), (WINDOW_WIDTH - 125, 335))
    for player, position in zip((1, 2, 3), cpu_positions):
        if player in state.rankings:
            status = f"{state.rankings.index(player) + 1}位"
        elif player in state.penalty_players:
            status = "ペナルティ"
        elif player in state.passed_players:
            status = "パス中"
        else:
            status = f"残り{len(state.hands[player])}枚"
        draw_text(screen, f"{PLAYER_NAMES[player]}：{status}", info_font, WHITE, position)

    draw_text(screen, table_description(state), info_font, WHITE, (WINDOW_WIDTH // 2, 225))
    draw_table_cards(screen, state.table_cards, card_font)

    message = state.message
    if len(message) > 52:
        message = message[:51] + "…"
    draw_text(screen, message, small_font, YELLOW, (WINDOW_WIDTH // 2, 405))

    human_turn = (
        not state.game_over
        and state.current_player == 0
        and state.pending_display is None
        and state.pending_selection is None
        and bool(state.hands[0])
    )
    if state.pending_selection and state.pending_selection.source_player == 0:
        action_label = "渡す" if state.pending_selection.action == "give" else "捨てる"
        confirm_enabled = len(state.selected_indices) == state.pending_selection.count
        draw_button(screen, PLAY_RECT, action_label, button_font, confirm_enabled)
        draw_button(screen, PASS_RECT, "選択解除", button_font, bool(state.selected_indices))
    else:
        draw_button(screen, PLAY_RECT, "出す", button_font, human_turn and bool(state.selected_indices))
        draw_button(screen, PASS_RECT, "パス", button_font, human_turn and state.table_pattern is not None)

    if 0 in state.rankings:
        human_status = f"{state.rankings.index(0) + 1}位"
    elif 0 in state.penalty_players:
        human_status = "ペナルティ"
    else:
        human_status = f"残り{len(state.hands[0])}枚"
    draw_text(screen, f"あなた：{human_status}", info_font, WHITE, (WINDOW_WIDTH // 2, 570))

    if state.pending_selection and state.pending_selection.source_player == 0:
        selection_text = f"{state.pending_selection.prompt}（{len(state.selected_indices)}/{state.pending_selection.count}）"
    else:
        selection_text = f"選択中：{len(state.selected_indices)}枚"
    draw_text(screen, selection_text, small_font, YELLOW, (WINDOW_WIDTH // 2, 600))
    draw_hand(screen, state.hands[0], state.selected_indices, card_font)

    for place, player in enumerate(state.rankings, 1):
        draw_text(screen, f"{place}位：{PLAYER_NAMES[player]}", small_font, WHITE, (985, 65 + place * 25))


def draw_result_screen(
    screen: pygame.Surface,
    state: GameState,
    title_font: pygame.font.Font,
    info_font: pygame.font.Font,
    small_font: pygame.font.Font,
    button_font: pygame.font.Font,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, f"第{state.session.round_number}戦　結果", title_font, YELLOW, (WINDOW_WIDTH // 2, 70))
    human_place = state.rankings.index(0) + 1
    draw_text(screen, f"あなたは{human_place}位（{RANK_TITLES[human_place - 1]}）でした", info_font, WHITE, (WINDOW_WIDTH // 2, 120))
    panel = pygame.Rect(285, 160, 530, 335)
    draw_panel(screen, panel)
    for place, player in enumerate(state.rankings, 1):
        color = YELLOW if player == 0 else WHITE
        draw_text(
            screen,
            f"{place}位　{RANK_TITLES[place - 1]}　{PLAYER_NAMES[player]}",
            info_font,
            color,
            (WINDOW_WIDTH // 2, 205 + (place - 1) * 70),
        )
    next_label = "次のラウンドへ（階級を引き継ぐ）"
    draw_button(screen, RESULT_NEXT_RECT, next_label, button_font)
    draw_button(screen, RESULT_RESET_RECT, "タイトルへ戻る", button_font)
    if state.rules.card_exchange:
        note = "次戦では階級に応じたカード交換が自動で行われます"
    elif state.rules.capital_fall:
        note = "次戦から都落ちの判定が有効になります"
    else:
        note = "次戦も同じルールで新しくカードを配ります"
    draw_text(screen, note, small_font, LIGHT_BLUE, (WINDOW_WIDTH // 2, 720))


def toggle_card_selection(state: GameState, position: tuple[int, int]) -> None:
    index = clicked_card_index(position, state.hands[0], state.selected_indices)
    if index is None:
        return
    if index in state.selected_indices:
        state.selected_indices.remove(index)
    else:
        state.selected_indices.add(index)


def handle_play_or_confirm(state: GameState) -> None:
    if state.pending_selection and state.pending_selection.source_player == 0:
        success, message = confirm_pending_selection(state, state.selected_indices)
        if not success:
            state.message = message
        return
    cards = [state.hands[0][index] for index in sorted(state.selected_indices)]
    success, message = play_cards(state, 0, cards)
    if not success:
        state.message = message


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("ルールを選べる大富豪")

    title_font = create_font(40, True)
    info_font = create_font(20, True)
    small_font = create_font(15, False)
    button_font = create_font(20, True)
    card_font = create_font(22, True)

    mode = "title"
    settings = RuleSettings.from_preset("standard")
    session: GameSession | None = None
    state: GameState | None = None
    clock = pygame.time.Clock()
    running = True

    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if mode == "title":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if TITLE_START_RECT.collidepoint(event.pos):
                        mode = "rules"
                    elif TITLE_QUIT_RECT.collidepoint(event.pos):
                        running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        mode = "rules"
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            elif mode == "rules":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    hit = False
                    for key, rect in rule_checkbox_rects().items():
                        if rect.collidepoint(event.pos):
                            setattr(settings, key, not bool(getattr(settings, key)))
                            # スペード3返しにはジョーカーが必要。
                            if key == "spade_three_return" and settings.spade_three_return:
                                settings.joker = True
                            if key == "joker" and not settings.joker:
                                settings.spade_three_return = False
                            hit = True
                            break
                    if hit:
                        continue
                    if RULE_BACK_RECT.collidepoint(event.pos):
                        mode = "title"
                    elif PRESET_SIMPLE_RECT.collidepoint(event.pos):
                        settings = RuleSettings.from_preset("simple")
                    elif PRESET_STANDARD_RECT.collidepoint(event.pos):
                        settings = RuleSettings.from_preset("standard")
                    elif PRESET_PARTY_RECT.collidepoint(event.pos):
                        settings = RuleSettings.from_preset("party")
                    elif RULE_START_RECT.collidepoint(event.pos):
                        session = GameSession(settings.copy())
                        state = create_game(session, now)
                        mode = "game"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    mode = "title"

            elif mode == "game":
                if state is None:
                    raise RuntimeError("ゲーム状態がありません。")
                can_touch_hand = (
                    state.current_player == 0
                    and not state.game_over
                    and state.pending_display is None
                    and (
                        state.pending_selection is None
                        or state.pending_selection.source_player == 0
                    )
                )
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if PLAY_RECT.collidepoint(event.pos):
                        handle_play_or_confirm(state)
                    elif PASS_RECT.collidepoint(event.pos):
                        if state.pending_selection and state.pending_selection.source_player == 0:
                            state.selected_indices.clear()
                        else:
                            success, message = pass_turn(state, 0)
                            if not success:
                                state.message = message
                    elif can_touch_hand:
                        toggle_card_selection(state, event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        state.selected_indices.clear()
                    elif event.key == pygame.K_RETURN and can_touch_hand:
                        handle_play_or_confirm(state)
                    elif event.key == pygame.K_p and can_touch_hand and state.pending_selection is None:
                        success, message = pass_turn(state, 0)
                        if not success:
                            state.message = message

            elif mode == "result":
                if state is None or session is None:
                    raise RuntimeError("ゲーム結果がありません。")
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if RESULT_NEXT_RECT.collidepoint(event.pos):
                        session.round_number += 1
                        state = create_game(session, now)
                        mode = "game"
                    elif RESULT_RESET_RECT.collidepoint(event.pos):
                        state = None
                        session = None
                        mode = "title"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        session.round_number += 1
                        state = create_game(session, now)
                        mode = "game"
                    elif event.key == pygame.K_ESCAPE:
                        state = None
                        session = None
                        mode = "title"

        if mode == "game" and state is not None:
            if state.turn_started_at == 0:
                state.turn_started_at = now

            if state.pending_display is not None:
                pending = state.pending_display
                if pending.started_at is not None and now - pending.started_at >= pending.duration_ms:
                    resolve_pending_display(state)
                    state.turn_started_at = now
            elif (
                not state.game_over
                and state.pending_selection is None
                and state.current_player != 0
                and now - state.turn_started_at >= CPU_TURN_DELAY_MS
            ):
                process_cpu_turn(state)
                if state.turn_started_at == 0:
                    state.turn_started_at = now

            if state.game_over and state.pending_display is None and state.pending_selection is None:
                mode = "result"

        if mode == "title":
            draw_title(screen, title_font, info_font, small_font, button_font, card_font)
        elif mode == "rules":
            draw_rules_screen(screen, settings, title_font, info_font, small_font, button_font)
        elif mode == "game":
            if state is None:
                raise RuntimeError("ゲーム状態がありません。")
            draw_game_screen(screen, state, title_font, info_font, small_font, button_font, card_font)
        else:
            if state is None:
                raise RuntimeError("ゲーム結果がありません。")
            draw_result_screen(screen, state, title_font, info_font, small_font, button_font)

        pygame.display.flip()

        if mode == "game" and state is not None and state.pending_display is not None:
            if state.pending_display.started_at is None:
                state.pending_display.started_at = pygame.time.get_ticks()

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
