from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import pygame

from app_settings import AppSettings, DIFFICULTY_LABELS, load_settings, save_settings
from card import Card
from card_art import CardFonts, draw_card_back, draw_card_front
from game_engine import (
    GameSession,
    GameState,
    PLAYER_NAMES,
    confirm_pending_selection,
    create_game,
    pass_turn,
    play_cards,
    process_cpu_turn,
    rank_titles_for,
    resolve_pending_display,
    state_status_lines,
    table_description,
)
from rules import RULE_INFOS, RuleSettings


WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 820
FPS = 60
CARD_WIDTH = 72
CARD_HEIGHT = 104
SELECTED_RAISE = 25
SETTINGS_PATH = Path(__file__).with_name("settings.json")

TABLE_COLOR = (31, 116, 72)
DARK_TABLE_COLOR = (15, 66, 45)
PANEL_COLOR = (24, 91, 59)
PANEL_DARK = (20, 75, 51)
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
YELLOW = (255, 222, 70)
LIGHT_BLUE = (164, 221, 255)
GREEN = (92, 220, 126)
GRAY = (150, 150, 150)
BUTTON_COLOR = (238, 238, 238)
BUTTON_HOVER = (255, 255, 255)
BUTTON_DISABLED = (145, 145, 145)
SELECTED_BUTTON = (121, 218, 147)
SHADOW_COLOR = (13, 65, 40)

TITLE_START_RECT = pygame.Rect(430, 380, 320, 60)
TITLE_SETTINGS_RECT = pygame.Rect(430, 455, 320, 55)
TITLE_HELP_RECT = pygame.Rect(430, 525, 320, 55)
TITLE_QUIT_RECT = pygame.Rect(430, 595, 320, 55)

SETTINGS_BACK_RECT = pygame.Rect(75, 730, 220, 55)
SETTINGS_RULES_RECT = pygame.Rect(430, 645, 320, 55)
SETTINGS_SAVE_RECT = pygame.Rect(850, 730, 255, 55)

RULE_BACK_RECT = pygame.Rect(75, 742, 220, 48)
RULE_SIMPLE_RECT = pygame.Rect(360, 742, 125, 48)
RULE_STANDARD_RECT = pygame.Rect(500, 742, 160, 48)
RULE_ALL_RECT = pygame.Rect(675, 742, 125, 48)
RULE_SAVE_STANDARD_RECT = pygame.Rect(275, 682, 300, 44)
RULE_RESET_STANDARD_RECT = pygame.Rect(605, 682, 300, 44)

HELP_BACK_RECT = pygame.Rect(455, 735, 270, 52)

PLAY_RECT = pygame.Rect(440, 545, 135, 48)
PASS_RECT = pygame.Rect(600, 545, 135, 48)
RESULT_NEXT_RECT = pygame.Rect(405, 640, 370, 58)
RESULT_TITLE_RECT = pygame.Rect(405, 710, 370, 50)

CPU_COUNT_RECTS = {
    1: pygame.Rect(390, 190, 120, 48),
    2: pygame.Rect(530, 190, 120, 48),
    3: pygame.Rect(670, 190, 120, 48),
}
DIFFICULTY_RECTS = {
    "easy": pygame.Rect(350, 315, 155, 48),
    "normal": pygame.Rect(525, 315, 155, 48),
    "hard": pygame.Rect(700, 315, 155, 48),
}
DEMO_RECT = pygame.Rect(350, 430, 500, 52)
PRESET_RECTS = {
    "simple": pygame.Rect(340, 550, 155, 48),
    "standard": pygame.Rect(515, 550, 155, 48),
    "party": pygame.Rect(690, 550, 155, 48),
}


@dataclass(slots=True)
class Fonts:
    title: pygame.font.Font
    heading: pygame.font.Font
    info: pygame.font.Font
    small: pygame.font.Font
    tiny: pygame.font.Font
    button: pygame.font.Font
    card: CardFonts


@dataclass(slots=True)
class PlayAnimation:
    cards: list[Card]
    player_index: int
    started_at: int
    duration_ms: int = 420

    def progress(self, now: int) -> float:
        return min(1.0, max(0.0, (now - self.started_at) / self.duration_ms))

    def finished(self, now: int) -> bool:
        return now - self.started_at >= self.duration_ms


def create_font(size: int, bold: bool = False) -> pygame.font.Font:
    """読みやすい日本語UIフォントを優先して読み込む。"""
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

    if bold:
        file_candidates = (
            "YuGothB.ttc",
            "meiryob.ttc",
            "BIZ-UDGothicB.ttc",
        )
    else:
        file_candidates = (
            "YuGothR.ttc",
            "YuGothM.ttc",
            "meiryo.ttc",
            "BIZ-UDGothicR.ttc",
        )

    for filename in file_candidates:
        path = windows_fonts / filename
        if path.exists():
            return pygame.font.Font(str(path), size)

    family_candidates = (
        "Yu Gothic UI",
        "Yu Gothic",
        "Meiryo UI",
        "Meiryo",
        "BIZ UDPGothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    )

    for family in family_candidates:
        path = pygame.font.match_font(family, bold=bold)
        if path:
            return pygame.font.Font(path, size)

    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font


def create_fonts() -> Fonts:
    return Fonts(
        title=create_font(46, True),
        heading=create_font(30, True),
        info=create_font(18, True),
        small=create_font(15, False),
        tiny=create_font(12, False),
        button=create_font(18, True),
        card=CardFonts(
            corner=create_font(14, True),
            suit=create_font(18, True),
            center=create_font(27, True),
            face=create_font(15, True),
            tiny=create_font(10, True),
        ),
    )

def draw_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))


def draw_text_left(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    left: int,
    center_y: int,
) -> None:
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(midleft=(left, center_y)))


def draw_fitted_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    padding_x: int = 14,
    padding_y: int = 8,
) -> None:
    """長い文字列もボタン内に収まるように縮小して描画する。"""
    surface = font.render(text, True, color)
    max_width = max(1, rect.width - padding_x * 2)
    max_height = max(1, rect.height - padding_y * 2)

    scale = min(
        1.0,
        max_width / max(1, surface.get_width()),
        max_height / max(1, surface.get_height()),
    )

    if scale < 1.0:
        new_size = (
            max(1, int(surface.get_width() * scale)),
            max(1, int(surface.get_height() * scale)),
        )
        surface = pygame.transform.smoothscale(surface, new_size)

    screen.blit(surface, surface.get_rect(center=rect.center))


def draw_text_right(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    right: int,
    center_y: int,
) -> None:
    """文字列の右端をそろえて描画する。"""
    surface = font.render(text, True, color)
    rect = surface.get_rect(midright=(right, center_y))
    screen.blit(surface, rect)


def draw_panel(screen: pygame.Surface, rect: pygame.Rect, dark: bool = False) -> None:
    pygame.draw.rect(screen, SHADOW_COLOR, rect.move(5, 6), border_radius=14)
    pygame.draw.rect(screen, PANEL_DARK if dark else PANEL_COLOR, rect, border_radius=14)
    pygame.draw.rect(screen, WHITE, rect, width=2, border_radius=14)


def draw_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    enabled: bool = True,
    selected: bool = False,
) -> None:
    mouse = pygame.mouse.get_pos()
    if not enabled:
        color = BUTTON_DISABLED
    elif selected:
        color = SELECTED_BUTTON
    elif rect.collidepoint(mouse):
        color = BUTTON_HOVER
    else:
        color = BUTTON_COLOR

    # わずかな影と細い枠で、重たく見えないUIにする。
    pygame.draw.rect(
        screen,
        (12, 55, 37),
        rect.move(0, 3),
        border_radius=10,
    )
    pygame.draw.rect(screen, color, rect, border_radius=10)
    border_color = WHITE if selected else (27, 51, 39)
    pygame.draw.rect(
        screen,
        border_color,
        rect,
        width=2 if selected else 1,
        border_radius=10,
    )
    draw_fitted_text(screen, label, font, BLACK, rect)


def human_card_rects(hand: list[Card], selected: set[int]) -> list[pygame.Rect]:
    if not hand:
        return []

    available_width = WINDOW_WIDTH - 54
    if len(hand) == 1:
        step = 0.0
        total_width = CARD_WIDTH
    else:
        normal_step = CARD_WIDTH + 6
        normal_total = CARD_WIDTH + normal_step * (len(hand) - 1)
        step = normal_step if normal_total <= available_width else (
            available_width - CARD_WIDTH
        ) / (len(hand) - 1)
        total_width = CARD_WIDTH + step * (len(hand) - 1)

    start_x = (WINDOW_WIDTH - total_width) / 2
    base_y = WINDOW_HEIGHT - CARD_HEIGHT - 17
    rects: list[pygame.Rect] = []

    for index in range(len(hand)):
        y = base_y - SELECTED_RAISE if index in selected else base_y
        rects.append(
            pygame.Rect(
                int(start_x + step * index),
                int(y),
                CARD_WIDTH,
                CARD_HEIGHT,
            )
        )

    return rects


def draw_human_hand(
    screen: pygame.Surface,
    hand: list[Card],
    selected: set[int],
    fonts: CardFonts,
) -> None:
    rects = human_card_rects(hand, selected)
    for index, card in enumerate(hand):
        draw_card_front(
            screen,
            card,
            rects[index],
            fonts,
            selected=index in selected,
        )


def clicked_card_index(
    position: tuple[int, int],
    hand: list[Card],
    selected: set[int],
) -> int | None:
    rects = human_card_rects(hand, selected)
    for index in range(len(rects) - 1, -1, -1):
        if rects[index].collidepoint(position):
            return index
    return None


def cpu_layout(player_count: int) -> dict[int, tuple[int, int, str]]:
    cpu_count = player_count - 1
    if cpu_count == 1:
        return {1: (WINDOW_WIDTH // 2, 155, "top")}
    if cpu_count == 2:
        return {
            1: (145, 325, "left"),
            2: (WINDOW_WIDTH - 145, 325, "right"),
        }
    return {
        1: (WINDOW_WIDTH // 2, 150, "top"),
        2: (135, 335, "left"),
        3: (WINDOW_WIDTH - 135, 335, "right"),
    }


def draw_cpu_back_fan(
    screen: pygame.Surface,
    center: tuple[int, int],
    orientation: str,
    count: int,
) -> None:
    visible = min(5, count)
    back_width = 42
    back_height = 60

    if orientation == "top":
        total = back_width + max(0, visible - 1) * 14
        start_x = center[0] - total // 2
        for index in range(visible):
            rect = pygame.Rect(start_x + index * 14, center[1] - 30, back_width, back_height)
            draw_card_back(screen, rect, draw_shadow=index == visible - 1)
    else:
        start_y = center[1] - (back_height + max(0, visible - 1) * 11) // 2
        x = center[0] - back_width // 2
        for index in range(visible):
            rect = pygame.Rect(x, start_y + index * 11, back_width, back_height)
            draw_card_back(screen, rect, draw_shadow=index == visible - 1)


def draw_table_cards(
    screen: pygame.Surface,
    cards: list[Card],
    fonts: CardFonts,
) -> None:
    if not cards:
        return
    gap = 8
    total = CARD_WIDTH * len(cards) + gap * (len(cards) - 1)
    start_x = (WINDOW_WIDTH - total) // 2
    for index, card in enumerate(cards):
        rect = pygame.Rect(
            start_x + index * (CARD_WIDTH + gap),
            305,
            CARD_WIDTH,
            CARD_HEIGHT,
        )
        draw_card_front(screen, card, rect, fonts)


def animation_start_position(player_index: int, player_count: int) -> tuple[int, int]:
    if player_index == 0:
        return WINDOW_WIDTH // 2, WINDOW_HEIGHT - 85
    x, y, _ = cpu_layout(player_count)[player_index]
    return x, y


def draw_play_animation(
    screen: pygame.Surface,
    animation: PlayAnimation,
    player_count: int,
    now: int,
    fonts: CardFonts,
) -> None:
    progress = animation.progress(now)
    eased = 1 - (1 - progress) ** 3
    start_x, start_y = animation_start_position(animation.player_index, player_count)
    target_y = 305
    gap = 8
    total = CARD_WIDTH * len(animation.cards) + gap * (len(animation.cards) - 1)
    target_start_x = (WINDOW_WIDTH - total) // 2

    for index, card in enumerate(animation.cards):
        target_x = target_start_x + index * (CARD_WIDTH + gap)
        x = int(start_x + (target_x - start_x) * eased)
        y = int(start_y + (target_y - start_y) * eased)
        rect = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)
        draw_card_front(screen, card, rect, fonts)


def draw_title(screen: pygame.Surface, fonts: Fonts) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "大富豪", fonts.title, WHITE, (WINDOW_WIDTH // 2, 90))

    samples = (
        Card("♠", "J"),
        Card("♥", "Q"),
        Card("♦", "K"),
        Card("JOKER", "JOKER"),
    )
    start_x = WINDOW_WIDTH // 2 - 180
    for index, card in enumerate(samples):
        draw_card_front(
            screen,
            card,
            pygame.Rect(start_x + index * 96, 165, CARD_WIDTH, CARD_HEIGHT),
            fonts.card,
        )

    draw_button(screen, TITLE_START_RECT, "ゲーム開始", fonts.button)
    draw_button(screen, TITLE_SETTINGS_RECT, "ゲーム設定", fonts.button)
    draw_button(screen, TITLE_HELP_RECT, "遊び方", fonts.button)
    draw_button(screen, TITLE_QUIT_RECT, "終了", fonts.button)
    draw_text(
        screen,
        "Enter：ゲーム開始　　Esc：終了",
        fonts.small,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 705),
    )


def draw_settings_screen(
    screen: pygame.Surface,
    settings: AppSettings,
    fonts: Fonts,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(
        screen,
        "ゲーム設定",
        fonts.heading,
        WHITE,
        (WINDOW_WIDTH // 2, 55),
    )

    panel = pygame.Rect(160, 105, 860, 545)
    draw_panel(screen, panel)

    label_x = panel.x + 48
    divider_color = (68, 139, 104)

    # CPU人数
    draw_text_left(screen, "CPU人数", fonts.info, WHITE, label_x, 158)
    draw_text_left(
        screen,
        "対戦するコンピューターの人数",
        fonts.tiny,
        (196, 222, 209),
        label_x,
        180,
    )
    for count, rect in CPU_COUNT_RECTS.items():
        draw_button(
            screen,
            rect,
            f"{count}人",
            fonts.button,
            selected=settings.cpu_count == count,
        )
    pygame.draw.line(screen, divider_color, (205, 270), (975, 270), 1)

    # CPU難易度
    draw_text_left(screen, "CPU難易度", fonts.info, WHITE, label_x, 283)
    draw_text_left(
        screen,
        "CPUがカードを選ぶ考え方を変更します",
        fonts.tiny,
        (196, 222, 209),
        label_x,
        305,
    )
    for key, rect in DIFFICULTY_RECTS.items():
        draw_button(
            screen,
            rect,
            DIFFICULTY_LABELS[key],
            fonts.button,
            selected=settings.cpu_difficulty == key,
        )
    pygame.draw.line(screen, divider_color, (205, 385), (975, 385), 1)

    # デモモード
    draw_text_left(screen, "デモモード", fonts.info, WHITE, label_x, 398)
    draw_text_left(
        screen,
        "特殊ルールを確認しやすい配札にします",
        fonts.tiny,
        (196, 222, 209),
        label_x,
        420,
    )
    demo_label = (
        "ON　特殊札を確認しやすい配札"
        if settings.demo_mode
        else "OFF　通常のランダム配札"
    )
    draw_button(
        screen,
        DEMO_RECT,
        demo_label,
        fonts.small,
        selected=settings.demo_mode,
    )
    pygame.draw.line(screen, divider_color, (205, 505), (975, 505), 1)

    # ルールプリセット
    draw_text_left(
        screen,
        "ルールプリセット",
        fonts.info,
        WHITE,
        label_x,
        518,
    )
    draw_text_left(
        screen,
        "標準はローカルルール詳細で自由に登録できます",
        fonts.tiny,
        (196, 222, 209),
        label_x,
        540,
    )
    simple_rules = RuleSettings.from_preset("simple")
    party_rules = RuleSettings.from_preset("party")

    for name, rect in PRESET_RECTS.items():
        label = {
            "simple": "基本のみ",
            "standard": "標準（編集可）",
            "party": "全部ON",
        }[name]

        if name == "simple":
            selected = settings.rules == simple_rules
        elif name == "standard":
            selected = settings.rules == settings.standard_rules
        else:
            selected = settings.rules == party_rules

        draw_button(
            screen,
            rect,
            label,
            fonts.small,
            selected=selected,
        )

    enabled_count = sum(settings.rules.to_dict().values())
    standard_count = sum(settings.standard_rules.to_dict().values())
    draw_text(
        screen,
        (
            f"現在ON　{enabled_count} / {len(RULE_INFOS)}　　"
            f"登録済み標準　{standard_count} / {len(RULE_INFOS)}"
        ),
        fonts.small,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 622),
    )

    draw_button(
        screen,
        SETTINGS_RULES_RECT,
        "ローカルルール詳細",
        fonts.button,
    )
    draw_button(
        screen,
        SETTINGS_BACK_RECT,
        "変更を戻して戻る",
        fonts.small,
    )
    draw_button(
        screen,
        SETTINGS_SAVE_RECT,
        "保存してタイトルへ",
        fonts.small,
    )

def rule_checkbox_rects() -> dict[str, pygame.Rect]:
    rects: dict[str, pygame.Rect] = {}
    for index, info in enumerate(RULE_INFOS):
        column = 0 if index < 7 else 1
        row = index if column == 0 else index - 7
        x = 65 if column == 0 else 600
        y = 105 + row * 82
        rects[info.key] = pygame.Rect(x, y, 515, 68)
    return rects


def draw_rules_screen(
    screen: pygame.Surface,
    settings: AppSettings,
    fonts: Fonts,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "ローカルルール", fonts.heading, WHITE, (WINDOW_WIDTH // 2, 45))
    current_count = sum(settings.rules.to_dict().values())
    standard_count = sum(settings.standard_rules.to_dict().values())
    draw_text(
        screen,
        (
            "クリックしてON／OFFを切り替えます　　"
            f"現在 {current_count}/{len(RULE_INFOS)}　"
            f"登録済み標準 {standard_count}/{len(RULE_INFOS)}"
        ),
        fonts.small,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 78),
    )

    mouse = pygame.mouse.get_pos()
    for info in RULE_INFOS:
        rect = rule_checkbox_rects()[info.key]
        enabled = bool(getattr(settings.rules, info.key))
        background = (31, 112, 72) if enabled else (53, 70, 62)
        if rect.collidepoint(mouse):
            background = (42, 132, 85) if enabled else (65, 84, 74)
        pygame.draw.rect(screen, background, rect, border_radius=10)
        pygame.draw.rect(screen, GREEN if enabled else GRAY, rect, width=2, border_radius=10)

        status_rect = pygame.Rect(rect.x + 12, rect.y + 17, 62, 34)
        pygame.draw.rect(screen, GREEN if enabled else GRAY, status_rect, border_radius=7)
        draw_text(screen, "ON" if enabled else "OFF", fonts.small, BLACK, status_rect.center)

        label = fonts.info.render(info.label, True, WHITE)
        screen.blit(label, (rect.x + 88, rect.y + 8))
        description = fonts.tiny.render(info.description, True, (221, 231, 226))
        screen.blit(description, (rect.x + 88, rect.y + 40))

    draw_button(
        screen,
        RULE_SAVE_STANDARD_RECT,
        "現在の組み合わせを標準に登録",
        fonts.small,
    )
    draw_button(
        screen,
        RULE_RESET_STANDARD_RECT,
        "標準を初期状態（7個）に戻す",
        fonts.small,
    )

    draw_button(screen, RULE_BACK_RECT, "設定画面へ戻る", fonts.small)
    draw_button(
        screen,
        RULE_SIMPLE_RECT,
        "基本のみ",
        fonts.small,
        selected=settings.rules == RuleSettings.from_preset("simple"),
    )
    draw_button(
        screen,
        RULE_STANDARD_RECT,
        "登録済み標準",
        fonts.small,
        selected=settings.rules == settings.standard_rules,
    )
    draw_button(
        screen,
        RULE_ALL_RECT,
        "全部ON",
        fonts.small,
        selected=settings.rules == RuleSettings.from_preset("party"),
    )


def draw_help_screen(screen: pygame.Surface, fonts: Fonts) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "遊び方", fonts.heading, WHITE, (WINDOW_WIDTH // 2, 60))
    panel = pygame.Rect(180, 115, 820, 565)
    draw_panel(screen, panel)

    sections = (
        ("基本操作", "カードをクリックして選択し、「出す」を押します。Pキーでパス、Escで選択解除できます。"),
        ("基本ルール", "場と同じ枚数・同じ種類で、より強い手を出します。全員がパスすると場が流れます。"),
        ("設定", "CPUは1〜3人、難易度は3段階です。採用するローカルルールも個別に選べます。"),
        ("デモモード", "革命・階段・8切り・スペード3返しなどを確認しやすい固定配札で開始します。"),
        ("カード", "J・Q・K・ジョーカーは、Pygameの図形だけで描いたオリジナルデザインです。"),
    )

    for index, (heading, body) in enumerate(sections):
        y = 165 + index * 98
        heading_surface = fonts.info.render(heading, True, YELLOW)
        screen.blit(heading_surface, (225, y))
        body_surface = fonts.small.render(body, True, WHITE)
        screen.blit(body_surface, (225, y + 35))

    draw_button(screen, HELP_BACK_RECT, "タイトルへ戻る", fonts.button)


def draw_game_screen(
    screen: pygame.Surface,
    state: GameState,
    fonts: Fonts,
    animation: PlayAnimation | None,
) -> None:
    screen.fill(TABLE_COLOR)
    draw_text(
        screen,
        f"大富豪　第{state.session.round_number}戦",
        fonts.heading,
        WHITE,
        (WINDOW_WIDTH // 2, 31),
    )

    if state.pending_display:
        turn_text = "8切り発動！" if state.pending_display.effect == "eight_cut" else "スペード3返し！"
        turn_color = YELLOW
    elif state.pending_selection:
        turn_text = "特殊効果のカードを選択中"
        turn_color = YELLOW
    elif state.game_over:
        turn_text = "ゲーム終了"
        turn_color = YELLOW
    elif animation is not None:
        turn_text = f"{PLAYER_NAMES[animation.player_index]}がカードを出しました"
        turn_color = LIGHT_BLUE
    else:
        turn_text = f"現在の番：{PLAYER_NAMES[state.current_player]}"
        turn_color = LIGHT_BLUE

    draw_text(screen, turn_text, fonts.info, turn_color, (WINDOW_WIDTH // 2, 70))

    statuses = state_status_lines(state)
    draw_text(
        screen,
        " / ".join(statuses),
        fonts.small,
        YELLOW if len(statuses) > 1 else WHITE,
        (160, 70),
    )

    settings_text = (
        f"CPU{state.session.player_count - 1}人・"
        f"{DIFFICULTY_LABELS[state.session.cpu_difficulty]}"
    )
    if state.session.demo_mode:
        settings_text += "・デモ"
    draw_text(screen, settings_text, fonts.tiny, LIGHT_BLUE, (1015, 70))

    layout = cpu_layout(len(state.hands))
    for player_index, (x, y, orientation) in layout.items():
        if player_index in state.rankings:
            status = f"{state.rankings.index(player_index) + 1}位"
        elif player_index in state.penalty_players:
            status = "ペナルティ"
        elif player_index in state.passed_players:
            status = "パス中"
        else:
            status = f"残り{len(state.hands[player_index])}枚"

        label_y = y - 62 if orientation == "top" else y - 70
        draw_text(
            screen,
            f"{PLAYER_NAMES[player_index]}：{status}",
            fonts.small,
            WHITE,
            (x, label_y),
        )
        draw_cpu_back_fan(screen, (x, y), orientation, len(state.hands[player_index]))

    draw_text(screen, table_description(state), fonts.info, WHITE, (WINDOW_WIDTH // 2, 255))
    if animation is None:
        draw_table_cards(screen, state.table_cards, fonts.card)

    message = state.message
    if len(message) > 64:
        message = message[:63] + "…"
    draw_text(screen, message, fonts.small, YELLOW, (WINDOW_WIDTH // 2, 455))

    human_turn = (
        not state.game_over
        and state.current_player == 0
        and state.pending_display is None
        and state.pending_selection is None
        and animation is None
        and bool(state.hands[0])
    )

    if state.pending_selection and state.pending_selection.source_player == 0:
        action_label = "渡す" if state.pending_selection.action == "give" else "捨てる"
        confirm_enabled = len(state.selected_indices) == state.pending_selection.count
        draw_button(screen, PLAY_RECT, action_label, fonts.button, confirm_enabled)
        draw_button(screen, PASS_RECT, "選択解除", fonts.button, bool(state.selected_indices))
    else:
        draw_button(
            screen,
            PLAY_RECT,
            "出す",
            fonts.button,
            human_turn and bool(state.selected_indices),
        )
        draw_button(
            screen,
            PASS_RECT,
            "パス",
            fonts.button,
            human_turn and state.table_pattern is not None,
        )

    if 0 in state.rankings:
        human_status = f"{state.rankings.index(0) + 1}位"
    elif 0 in state.penalty_players:
        human_status = "ペナルティ"
    else:
        human_status = f"残り{len(state.hands[0])}枚"

    draw_text(screen, f"あなた：{human_status}", fonts.info, WHITE, (WINDOW_WIDTH // 2, 625))

    if state.pending_selection and state.pending_selection.source_player == 0:
        selection_text = (
            f"{state.pending_selection.prompt}"
            f"（{len(state.selected_indices)}/{state.pending_selection.count}）"
        )
    else:
        selection_text = f"選択中：{len(state.selected_indices)}枚"

    draw_text(screen, selection_text, fonts.small, YELLOW, (WINDOW_WIDTH // 2, 653))
    draw_human_hand(screen, state.hands[0], state.selected_indices, fonts.card)

    for place, player in enumerate(state.rankings, 1):
        draw_text(
            screen,
            f"{place}位：{PLAYER_NAMES[player]}",
            fonts.tiny,
            WHITE,
            (1080, 105 + place * 24),
        )


def draw_result_screen(screen: pygame.Surface, state: GameState, fonts: Fonts) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(
        screen,
        f"第{state.session.round_number}戦　結果",
        fonts.heading,
        YELLOW,
        (WINDOW_WIDTH // 2, 65),
    )

    human_place = state.rankings.index(0) + 1
    titles = rank_titles_for(len(state.hands))
    draw_text(
        screen,
        f"あなたは{human_place}位（{titles[human_place - 1]}）でした",
        fonts.info,
        WHITE,
        (WINDOW_WIDTH // 2, 112),
    )

    row_height = 82
    panel_height = 70 + row_height * len(state.rankings)
    panel = pygame.Rect(300, 150, 580, panel_height)
    draw_panel(screen, panel)

    for place, player in enumerate(state.rankings, 1):
        color = YELLOW if player == 0 else WHITE
        draw_text(
            screen,
            f"{place}位　{titles[place - 1]}　{PLAYER_NAMES[player]}",
            fonts.info,
            color,
            (WINDOW_WIDTH // 2, 195 + (place - 1) * row_height),
        )

    draw_button(screen, RESULT_NEXT_RECT, "次のラウンドへ", fonts.button)
    draw_button(screen, RESULT_TITLE_RECT, "タイトルへ戻る", fonts.button)


def toggle_card_selection(state: GameState, position: tuple[int, int]) -> None:
    index = clicked_card_index(position, state.hands[0], state.selected_indices)
    if index is None:
        return
    if index in state.selected_indices:
        state.selected_indices.remove(index)
    else:
        state.selected_indices.add(index)


def handle_play_or_confirm(
    state: GameState,
    now: int,
) -> PlayAnimation | None:
    if state.pending_selection and state.pending_selection.source_player == 0:
        success, message = confirm_pending_selection(state, state.selected_indices)
        if not success:
            state.message = message
        return None

    cards = [state.hands[0][index] for index in sorted(state.selected_indices)]
    success, message = play_cards(state, 0, cards)
    if not success:
        state.message = message
        return None

    return PlayAnimation(list(state.table_cards), 0, now)


def start_game(settings: AppSettings, now: int) -> tuple[GameSession, GameState]:
    session = GameSession(
        settings.rules.copy(),
        player_count=settings.player_count,
        cpu_difficulty=settings.cpu_difficulty,
        demo_mode=settings.demo_mode,
    )
    return session, create_game(session, now)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("大富豪")
    fonts = create_fonts()

    settings = load_settings(SETTINGS_PATH)
    editing_settings: AppSettings | None = None
    mode = "title"
    session: GameSession | None = None
    state: GameState | None = None
    animation: PlayAnimation | None = None

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
                        session, state = start_game(settings, now)
                        animation = None
                        mode = "game"
                    elif TITLE_SETTINGS_RECT.collidepoint(event.pos):
                        editing_settings = AppSettings.from_dict(settings.to_dict())
                        mode = "settings"
                    elif TITLE_HELP_RECT.collidepoint(event.pos):
                        mode = "help"
                    elif TITLE_QUIT_RECT.collidepoint(event.pos):
                        running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        session, state = start_game(settings, now)
                        animation = None
                        mode = "game"
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            elif mode == "settings":
                if editing_settings is None:
                    editing_settings = AppSettings.from_dict(settings.to_dict())

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    handled = False
                    for count, rect in CPU_COUNT_RECTS.items():
                        if rect.collidepoint(event.pos):
                            editing_settings.cpu_count = count
                            handled = True
                            break
                    if handled:
                        continue

                    for difficulty, rect in DIFFICULTY_RECTS.items():
                        if rect.collidepoint(event.pos):
                            editing_settings.cpu_difficulty = difficulty
                            handled = True
                            break
                    if handled:
                        continue

                    if DEMO_RECT.collidepoint(event.pos):
                        editing_settings.demo_mode = not editing_settings.demo_mode
                    elif PRESET_RECTS["simple"].collidepoint(event.pos):
                        editing_settings.rules = RuleSettings.from_preset("simple")
                    elif PRESET_RECTS["standard"].collidepoint(event.pos):
                        editing_settings.rules = editing_settings.standard_rules.copy()
                    elif PRESET_RECTS["party"].collidepoint(event.pos):
                        editing_settings.rules = RuleSettings.from_preset("party")
                    elif SETTINGS_RULES_RECT.collidepoint(event.pos):
                        mode = "rules"
                    elif SETTINGS_BACK_RECT.collidepoint(event.pos):
                        editing_settings = None
                        mode = "title"
                    elif SETTINGS_SAVE_RECT.collidepoint(event.pos):
                        settings = editing_settings
                        save_settings(SETTINGS_PATH, settings)
                        editing_settings = None
                        mode = "title"

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    editing_settings = None
                    mode = "title"

            elif mode == "rules":
                if editing_settings is None:
                    editing_settings = AppSettings.from_dict(settings.to_dict())

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    hit_rule = False
                    for key, rect in rule_checkbox_rects().items():
                        if rect.collidepoint(event.pos):
                            setattr(
                                editing_settings.rules,
                                key,
                                not bool(getattr(editing_settings.rules, key)),
                            )
                            if key == "spade_three_return" and editing_settings.rules.spade_three_return:
                                editing_settings.rules.joker = True
                            if key == "joker" and not editing_settings.rules.joker:
                                editing_settings.rules.spade_three_return = False
                            hit_rule = True
                            break
                    if hit_rule:
                        continue

                    if RULE_BACK_RECT.collidepoint(event.pos):
                        mode = "settings"
                    elif RULE_SAVE_STANDARD_RECT.collidepoint(event.pos):
                        editing_settings.standard_rules = editing_settings.rules.copy()
                    elif RULE_RESET_STANDARD_RECT.collidepoint(event.pos):
                        editing_settings.standard_rules = RuleSettings.from_preset(
                            "standard"
                        )
                        editing_settings.rules = editing_settings.standard_rules.copy()
                    elif RULE_SIMPLE_RECT.collidepoint(event.pos):
                        editing_settings.rules = RuleSettings.from_preset("simple")
                    elif RULE_STANDARD_RECT.collidepoint(event.pos):
                        editing_settings.rules = editing_settings.standard_rules.copy()
                    elif RULE_ALL_RECT.collidepoint(event.pos):
                        editing_settings.rules = RuleSettings.from_preset("party")

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    mode = "settings"

            elif mode == "help":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if HELP_BACK_RECT.collidepoint(event.pos):
                        mode = "title"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    mode = "title"

            elif mode == "game":
                if state is None:
                    raise RuntimeError("ゲーム状態がありません。")

                can_touch_hand = (
                    animation is None
                    and state.current_player == 0
                    and not state.game_over
                    and state.pending_display is None
                    and (
                        state.pending_selection is None
                        or state.pending_selection.source_player == 0
                    )
                )

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if animation is not None:
                        continue
                    if PLAY_RECT.collidepoint(event.pos):
                        animation = handle_play_or_confirm(state, now)
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
                        animation = handle_play_or_confirm(state, now)
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
                        animation = None
                        mode = "game"
                    elif RESULT_TITLE_RECT.collidepoint(event.pos):
                        state = None
                        session = None
                        animation = None
                        mode = "title"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        session.round_number += 1
                        state = create_game(session, now)
                        animation = None
                        mode = "game"
                    elif event.key == pygame.K_ESCAPE:
                        state = None
                        session = None
                        animation = None
                        mode = "title"

        if mode == "game" and state is not None:
            if animation is not None and animation.finished(now):
                animation = None
                if state.turn_started_at == 0:
                    state.turn_started_at = now

            if animation is None:
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
                    and now - state.turn_started_at >= {
                        "easy": 950,
                        "normal": 780,
                        "hard": 650,
                    }[state.session.cpu_difficulty]
                ):
                    cpu_player = state.current_player
                    before_count = len(state.hands[cpu_player])
                    process_cpu_turn(state)
                    if (
                        len(state.hands[cpu_player]) < before_count
                        and state.last_played_player == cpu_player
                        and state.table_cards
                    ):
                        animation = PlayAnimation(list(state.table_cards), cpu_player, now)
                    if state.turn_started_at == 0:
                        state.turn_started_at = now

            if (
                state.game_over
                and animation is None
                and state.pending_display is None
                and state.pending_selection is None
            ):
                mode = "result"

        if mode == "title":
            draw_title(screen, fonts)
        elif mode == "settings":
            if editing_settings is None:
                editing_settings = AppSettings.from_dict(settings.to_dict())
            draw_settings_screen(screen, editing_settings, fonts)
        elif mode == "rules":
            if editing_settings is None:
                editing_settings = AppSettings.from_dict(settings.to_dict())
            draw_rules_screen(screen, editing_settings, fonts)
        elif mode == "help":
            draw_help_screen(screen, fonts)
        elif mode == "game":
            if state is None:
                raise RuntimeError("ゲーム状態がありません。")
            draw_game_screen(screen, state, fonts, animation)
            if animation is not None:
                draw_play_animation(
                    screen,
                    animation,
                    len(state.hands),
                    now,
                    fonts.card,
                )
        else:
            if state is None:
                raise RuntimeError("ゲーム結果がありません。")
            draw_result_screen(screen, state, fonts)

        pygame.display.flip()

        if (
            mode == "game"
            and state is not None
            and animation is None
            and state.pending_display is not None
            and state.pending_display.started_at is None
        ):
            state.pending_display.started_at = pygame.time.get_ticks()

        clock.tick(FPS)

    save_settings(SETTINGS_PATH, settings)
    pygame.quit()


if __name__ == "__main__":
    main()
