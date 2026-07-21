from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import queue
import socket
import threading
from typing import Any

import pygame

from card import Card
from card_art import CardFonts, draw_card_back, draw_card_front
from lan_common import card_from_dict, card_id
from lan_protocol import receive_messages, send_message

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 820
FPS = 60
DEFAULT_PORT = 50000
CARD_WIDTH = 72
CARD_HEIGHT = 104
SELECTED_RAISE = 25

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
RED = (230, 95, 95)
BUTTON_COLOR = (238, 238, 238)
BUTTON_HOVER = (255, 255, 255)
BUTTON_DISABLED = (145, 145, 145)
SELECTED_BUTTON = (121, 218, 147)
SHADOW_COLOR = (13, 65, 40)

CONNECT_HOST_RECT = pygame.Rect(350, 270, 480, 52)
CONNECT_NAME_RECT = pygame.Rect(350, 365, 480, 52)
CONNECT_BUTTON_RECT = pygame.Rect(430, 475, 320, 58)
LOBBY_MINUS_RECT = pygame.Rect(385, 610, 56, 48)
LOBBY_PLUS_RECT = pygame.Rect(740, 610, 56, 48)
LOBBY_START_RECT = pygame.Rect(430, 690, 320, 58)
PLAY_RECT = pygame.Rect(440, 595, 135, 48)
PASS_RECT = pygame.Rect(600, 595, 135, 48)
NEXT_ROUND_RECT = pygame.Rect(405, 690, 370, 58)


@dataclass(slots=True)
class Fonts:
    title: pygame.font.Font
    heading: pygame.font.Font
    info: pygame.font.Font
    small: pygame.font.Font
    tiny: pygame.font.Font
    button: pygame.font.Font
    card: CardFonts


class NetworkClient:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.connected = False
        self.error: str | None = None

    def connect(self, host: str, port: int, name: str) -> None:
        if self.connected:
            return

        def worker() -> None:
            try:
                sock = socket.create_connection((host, port), timeout=7.0)
                sock.settimeout(None)
                self.sock = sock
                send_message(sock, {"type": "join", "name": name}, self.send_lock)
                self.connected = True
                for message in receive_messages(sock):
                    self.messages.put(message)
            except (OSError, ValueError) as exc:
                self.error = str(exc)
                self.messages.put({"type": "network_error", "message": str(exc)})
            finally:
                self.connected = False

        threading.Thread(target=worker, daemon=True).start()

    def send(self, message: dict[str, Any]) -> None:
        if self.sock is None or not self.connected:
            return
        try:
            send_message(self.sock, message, self.send_lock)
        except OSError as exc:
            self.messages.put({"type": "network_error", "message": str(exc)})

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self.sock = None
        self.connected = False


def create_font(size: int, bold: bool = False) -> pygame.font.Font:
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    file_candidates = (
        ("YuGothB.ttc", "meiryob.ttc", "BIZ-UDGothicB.ttc")
        if bold
        else ("YuGothR.ttc", "YuGothM.ttc", "meiryo.ttc", "BIZ-UDGothicR.ttc")
    )
    for filename in file_candidates:
        path = windows_fonts / filename
        if path.exists():
            return pygame.font.Font(str(path), size)

    for family in (
        "Yu Gothic UI",
        "Yu Gothic",
        "Meiryo UI",
        "Meiryo",
        "BIZ UDPGothic",
        "Noto Sans CJK JP",
    ):
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
        small=create_font(15),
        tiny=create_font(12),
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


def draw_panel(screen: pygame.Surface, rect: pygame.Rect, dark: bool = False) -> None:
    pygame.draw.rect(screen, SHADOW_COLOR, rect.move(5, 6), border_radius=16)
    pygame.draw.rect(screen, PANEL_DARK if dark else PANEL_COLOR, rect, border_radius=16)
    pygame.draw.rect(screen, (220, 244, 232), rect, width=2, border_radius=16)


def draw_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    enabled: bool = True,
    selected: bool = False,
) -> None:
    hovered = enabled and rect.collidepoint(pygame.mouse.get_pos())
    if not enabled:
        color = BUTTON_DISABLED
    elif selected:
        color = SELECTED_BUTTON
    elif hovered:
        color = BUTTON_HOVER
    else:
        color = BUTTON_COLOR
    pygame.draw.rect(screen, SHADOW_COLOR, rect.move(3, 4), border_radius=10)
    pygame.draw.rect(screen, color, rect, border_radius=10)
    pygame.draw.rect(screen, (25, 48, 37), rect, width=2, border_radius=10)
    draw_text(screen, text, font, BLACK, rect.center)


def draw_input(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    value: str,
    font: pygame.font.Font,
    active: bool,
) -> None:
    draw_text_left(screen, label, font, WHITE, rect.left, rect.top - 20)
    pygame.draw.rect(screen, WHITE, rect, border_radius=9)
    pygame.draw.rect(screen, YELLOW if active else (50, 72, 61), rect, width=3, border_radius=9)
    shown = value + ("|" if active and (pygame.time.get_ticks() // 500) % 2 == 0 else "")
    draw_text_left(screen, shown, font, BLACK, rect.left + 14, rect.centery)


def hand_rects(hand: list[Card], selected_ids: set[str]) -> list[pygame.Rect]:
    if not hand:
        return []
    available = WINDOW_WIDTH - 50
    if len(hand) == 1:
        step = 0.0
        total = CARD_WIDTH
    else:
        normal_step = CARD_WIDTH + 6
        total_normal = CARD_WIDTH + normal_step * (len(hand) - 1)
        step = normal_step if total_normal <= available else (available - CARD_WIDTH) / (len(hand) - 1)
        total = CARD_WIDTH + step * (len(hand) - 1)
    start_x = int((WINDOW_WIDTH - total) / 2)
    base_y = WINDOW_HEIGHT - CARD_HEIGHT - 25
    rects: list[pygame.Rect] = []
    for index, card in enumerate(hand):
        y = base_y - SELECTED_RAISE if card_id(card) in selected_ids else base_y
        rects.append(pygame.Rect(int(start_x + step * index), y, CARD_WIDTH, CARD_HEIGHT))
    return rects


def bright_card_ids(
    hand: list[Card],
    selected_ids: set[str],
    game: dict[str, Any],
    seat: int,
) -> set[str]:
    pending = game.get("pending_selection")
    if isinstance(pending, dict) and pending.get("source_player") == seat:
        count = int(pending.get("count", 0))
        if len(selected_ids) < count:
            return {card_id(card) for card in hand}
        return set(selected_ids)

    if game.get("current_player") != seat or game.get("pending_display") is not None:
        return set()

    legal_raw = game.get("legal_plays", [])
    selected = set(selected_ids)
    bright: set[str] = set(selected)
    if isinstance(legal_raw, list):
        for play in legal_raw:
            if not isinstance(play, list):
                continue
            play_set = {str(item) for item in play}
            if selected.issubset(play_set):
                bright.update(play_set)
    return bright


def draw_hand(
    screen: pygame.Surface,
    hand: list[Card],
    selected_ids: set[str],
    bright_ids: set[str],
    fonts: CardFonts,
) -> list[pygame.Rect]:
    rects = hand_rects(hand, selected_ids)
    for index, card in enumerate(hand):
        cid = card_id(card)
        draw_card_front(
            screen,
            card,
            rects[index],
            fonts,
            selected=cid in selected_ids,
            dimmed=cid not in bright_ids and cid not in selected_ids,
        )
    return rects


def opponent_positions() -> list[tuple[int, int, str]]:
    return [
        (180, 170, "top"),
        (590, 120, "top"),
        (1000, 170, "top"),
        (1030, 395, "right"),
        (150, 395, "left"),
    ]


def draw_back_fan(
    screen: pygame.Surface,
    center: tuple[int, int],
    orientation: str,
    count: int,
) -> None:
    visible = min(5, count)
    w, h = 38, 54
    if orientation == "top":
        step = 12
        total = w + max(0, visible - 1) * step
        x0 = center[0] - total // 2
        y0 = center[1]
        for i in range(visible):
            draw_card_back(screen, pygame.Rect(x0 + i * step, y0, w, h), draw_shadow=i == visible - 1)
    else:
        step = 10
        x0 = center[0] - w // 2
        y0 = center[1] - (h + max(0, visible - 1) * step) // 2
        for i in range(visible):
            draw_card_back(screen, pygame.Rect(x0, y0 + i * step, w, h), draw_shadow=i == visible - 1)


def relative_opponents(seat: int, player_count: int) -> list[int]:
    return [((seat + offset) % player_count) for offset in range(1, player_count)]


def draw_connect(
    screen: pygame.Surface,
    fonts: Fonts,
    host_value: str,
    name_value: str,
    active_field: str | None,
    status: str,
) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "LAN大富豪", fonts.title, WHITE, (WINDOW_WIDTH // 2, 105))
    draw_text(
        screen,
        "同じWi-FiまたはLANに接続したPC同士で対戦します",
        fonts.info,
        LIGHT_BLUE,
        (WINDOW_WIDTH // 2, 165),
    )
    draw_panel(screen, pygame.Rect(285, 220, 610, 390), dark=True)
    draw_input(screen, CONNECT_HOST_RECT, "ホストPCのIPv4アドレス", host_value, fonts.info, active_field == "host")
    draw_input(screen, CONNECT_NAME_RECT, "あなたの名前", name_value, fonts.info, active_field == "name")
    draw_button(screen, CONNECT_BUTTON_RECT, "部屋に参加", fonts.button, enabled=bool(host_value.strip() and name_value.strip()))
    draw_text(screen, status, fonts.small, YELLOW if status else WHITE, (WINDOW_WIDTH // 2, 565))
    draw_text(screen, "ホストPC自身は 127.0.0.1 で接続できます", fonts.small, WHITE, (WINDOW_WIDTH // 2, 650))


def draw_lobby(screen: pygame.Surface, fonts: Fonts, snapshot: dict[str, Any]) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "LAN対戦ロビー", fonts.title, WHITE, (WINDOW_WIDTH // 2, 70))
    connected = set(int(x) for x in snapshot.get("connected", []))
    names = [str(x) for x in snapshot.get("names", ["-"] * 6)]
    seat = int(snapshot.get("seat", -1))
    host_seat = snapshot.get("host_seat")
    target = int(snapshot.get("player_count", 6))
    max_players = int(snapshot.get("max_player_count", 6))
    min_players = int(snapshot.get("min_player_count", 2))
    can_start = bool(snapshot.get("can_start", False))
    panel = pygame.Rect(270, 125, 640, 455)
    draw_panel(screen, panel)

    for index in range(max_players):
        y = 168 + index * 58
        occupied = index in connected
        in_game = index < target
        if occupied:
            color = GREEN
            name = names[index] if index < len(names) else "-"
            marker = "（あなた）" if index == seat else ""
            host_marker = "　ホスト" if index == host_seat else ""
            text = f"{name}{marker}{host_marker}"
        elif in_game:
            color = LIGHT_BLUE
            text = "CPU"
        else:
            color = GRAY
            text = "未使用"
        draw_text_left(screen, f"席{index + 1}", fonts.info, color, 345, y)
        draw_text_left(screen, text, fonts.info, WHITE if in_game or occupied else GRAY, 455, y)

    cpu_count = sum(1 for index in range(target) if index not in connected)
    draw_text(screen, f"対戦人数 {target}人　CPU {cpu_count}人", fonts.heading, LIGHT_BLUE, (WINDOW_WIDTH // 2, 612))

    if seat == host_seat:
        draw_button(screen, LOBBY_MINUS_RECT, "-", fonts.button, enabled=target > max(min_players, max(connected, default=-1) + 1))
        draw_button(screen, LOBBY_PLUS_RECT, "+", fonts.button, enabled=target < max_players)
        draw_text(screen, "ホストが人数を変更できます", fonts.small, WHITE, (WINDOW_WIDTH // 2, 660))
        draw_button(screen, LOBBY_START_RECT, "この人数で開始", fonts.button, enabled=can_start)
    else:
        draw_text(screen, "ホストが人数を決めて開始します", fonts.info, WHITE, (WINDOW_WIDTH // 2, 704))


def draw_table_cards(screen: pygame.Surface, cards: list[Card], fonts: CardFonts) -> None:
    if not cards:
        return
    gap = 8
    total = CARD_WIDTH * len(cards) + gap * (len(cards) - 1)
    start_x = (WINDOW_WIDTH - total) // 2
    for i, card in enumerate(cards):
        draw_card_front(screen, card, pygame.Rect(start_x + i * (CARD_WIDTH + gap), 315, CARD_WIDTH, CARD_HEIGHT), fonts)


def draw_game(screen: pygame.Surface, fonts: Fonts, snapshot: dict[str, Any], selected_ids: set[str]) -> list[pygame.Rect]:
    screen.fill(TABLE_COLOR)
    seat = int(snapshot["seat"])
    names = [str(x) for x in snapshot.get("names", [])]
    player_count = int(snapshot.get("player_count", len(names) or 6))
    game = snapshot.get("game") or {}
    hand = [card_from_dict(x) for x in game.get("hand", [])]
    table_cards = [card_from_dict(x) for x in game.get("table_cards", [])]
    counts = [int(x) for x in game.get("card_counts", [0] * player_count)]
    current = int(game.get("current_player", -1))
    passed = {int(x) for x in game.get("passed_players", [])}
    rankings = [int(x) for x in game.get("rankings", [])]

    draw_text(screen, f"第{game.get('round_number', 1)}戦　{player_count}人LAN大富豪", fonts.heading, WHITE, (WINDOW_WIDTH // 2, 34))
    status = []
    if game.get("revolution"):
        status.append("革命")
    if game.get("eleven_back"):
        status.append("11バック")
    locked = game.get("locked_suits")
    if locked:
        status.append("縛り:" + "・".join(str(x) for x in locked))
    draw_text(screen, " / ".join(status) if status else "通常", fonts.small, YELLOW if status else WHITE, (160, 35))

    opponents = relative_opponents(seat, player_count)
    for opponent, (x, y, orientation) in zip(opponents, opponent_positions()):
        count = counts[opponent]
        draw_back_fan(screen, (x, y), orientation, count)
        name = names[opponent] if opponent < len(names) else f"席{opponent + 1}"
        if opponent in rankings:
            label = f"{name}　{rankings.index(opponent) + 1}位"
            color = YELLOW
        elif opponent in passed:
            label = f"{name}　パス"
            color = GRAY
        else:
            label = f"{name}　残り{count}枚"
            color = LIGHT_BLUE if opponent == current else WHITE
        label_y = y - 28 if orientation == "top" else y - 60
        draw_text(screen, label, fonts.small, color, (x, label_y))

    turn_name = names[current] if 0 <= current < len(names) else "-"
    draw_text(screen, f"現在の番：{turn_name}", fonts.info, LIGHT_BLUE, (WINDOW_WIDTH // 2, 195))
    draw_text(screen, str(game.get("table_description", "場：なし")), fonts.info, WHITE, (WINDOW_WIDTH // 2, 255))
    draw_table_cards(screen, table_cards, fonts.card)
    draw_text(screen, str(game.get("message", "")), fonts.small, YELLOW, (WINDOW_WIDTH // 2, 455))

    pending = game.get("pending_selection")
    if isinstance(pending, dict) and pending.get("source_player") == seat:
        prompt = str(pending.get("prompt", "カードを選択してください"))
        selection_text = f"{prompt}　選択 {len(selected_ids)} / {pending.get('count', 0)}"
        button_text = "渡す" if pending.get("action") == "give" else "捨てる"
        ready = len(selected_ids) == int(pending.get("count", 0))
        draw_button(screen, PLAY_RECT, button_text, fonts.button, enabled=ready)
        draw_button(screen, PASS_RECT, "パス不可", fonts.button, enabled=False)
    else:
        selection_text = f"選択中：{len(selected_ids)}枚"
        human_turn = current == seat and game.get("pending_display") is None and not game.get("game_over")
        draw_button(screen, PLAY_RECT, "出す", fonts.button, enabled=human_turn and bool(selected_ids))
        draw_button(screen, PASS_RECT, "パス", fonts.button, enabled=human_turn and bool(table_cards))

    draw_text(screen, selection_text, fonts.small, YELLOW, (WINDOW_WIDTH // 2, 650))
    bright = bright_card_ids(hand, selected_ids, game, seat)
    rects = draw_hand(screen, hand, selected_ids, bright, fonts.card)
    your_name = names[seat] if seat < len(names) else "-"
    draw_text(screen, f"あなた：{your_name}　残り{len(hand)}枚", fonts.info, WHITE, (WINDOW_WIDTH // 2, 695))
    return rects


def draw_result(screen: pygame.Surface, fonts: Fonts, snapshot: dict[str, Any]) -> None:
    screen.fill(DARK_TABLE_COLOR)
    draw_text(screen, "対戦結果", fonts.title, YELLOW, (WINDOW_WIDTH // 2, 75))
    game = snapshot.get("game") or {}
    names = [str(x) for x in snapshot.get("names", [])]
    rankings = [int(x) for x in game.get("rankings", [])]
    titles = [str(x) for x in game.get("rank_titles", [])]
    seat = int(snapshot.get("seat", -1))
    host_seat = snapshot.get("host_seat")
    draw_panel(screen, pygame.Rect(300, 135, 580, 495))
    for place, player in enumerate(rankings, start=1):
        color = YELLOW if player == seat else WHITE
        title = titles[place - 1] if place - 1 < len(titles) else f"{place}位"
        name = names[player] if player < len(names) else f"席{player + 1}"
        draw_text(screen, f"{place}位　{title}　{name}", fonts.info, color, (WINDOW_WIDTH // 2, 185 + (place - 1) * 68))
    if seat == host_seat:
        draw_button(screen, NEXT_ROUND_RECT, "次のラウンドへ", fonts.button)
    else:
        draw_text(screen, "ホストが次のラウンドを開始するまでお待ちください", fonts.info, WHITE, (WINDOW_WIDTH // 2, 720))


def clicked_card(position: tuple[int, int], rects: list[pygame.Rect]) -> int | None:
    for index in range(len(rects) - 1, -1, -1):
        if rects[index].collidepoint(position):
            return index
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN大富豪クライアント")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--name", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("LAN大富豪")
    fonts = create_fonts()
    clock = pygame.time.Clock()
    network = NetworkClient()

    host_value = args.host or "127.0.0.1"
    name_value = args.name or ""
    active_field: str | None = "name" if not args.name else None
    status = ""
    snapshot: dict[str, Any] | None = None
    selected_ids: set[str] = set()
    connecting = False
    hand_rect_cache: list[pygame.Rect] = []
    running = True

    if args.host and args.name:
        network.connect(args.host, args.port, args.name)
        connecting = True
        status = "接続中..."

    while running:
        while True:
            try:
                message = network.messages.get_nowait()
            except queue.Empty:
                break
            message_type = message.get("type")
            if message_type == "state":
                snapshot = message
                connecting = False
                status = ""
                game = snapshot.get("game")
                if isinstance(game, dict):
                    current_ids = {card_id(card_from_dict(x)) for x in game.get("hand", [])}
                    selected_ids.intersection_update(current_ids)
            elif message_type == "welcome":
                connecting = False
                status = "接続しました"
            elif message_type in ("error", "network_error"):
                connecting = False
                status = str(message.get("message", "通信エラー"))

        phase = snapshot.get("phase") if snapshot else "connect"

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if snapshot is None:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if CONNECT_HOST_RECT.collidepoint(event.pos):
                        active_field = "host"
                    elif CONNECT_NAME_RECT.collidepoint(event.pos):
                        active_field = "name"
                    elif CONNECT_BUTTON_RECT.collidepoint(event.pos) and not connecting:
                        if host_value.strip() and name_value.strip():
                            network.connect(host_value.strip(), args.port, name_value.strip())
                            connecting = True
                            status = "接続中..."
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        active_field = "name" if active_field == "host" else "host"
                    elif event.key == pygame.K_RETURN and not connecting:
                        if host_value.strip() and name_value.strip():
                            network.connect(host_value.strip(), args.port, name_value.strip())
                            connecting = True
                            status = "接続中..."
                    elif event.key == pygame.K_BACKSPACE:
                        if active_field == "host":
                            host_value = host_value[:-1]
                        elif active_field == "name":
                            name_value = name_value[:-1]
                    elif event.unicode and event.unicode.isprintable():
                        if active_field == "host" and len(host_value) < 40:
                            host_value += event.unicode
                        elif active_field == "name" and len(name_value) < 16:
                            name_value += event.unicode
                continue

            if phase == "lobby":
                target = int(snapshot.get("player_count", 6))
                max_players = int(snapshot.get("max_player_count", 6))
                min_players = int(snapshot.get("min_player_count", 2))
                connected = [int(x) for x in snapshot.get("connected", [])]
                min_allowed = max(min_players, max(connected, default=-1) + 1)
                seat = int(snapshot.get("seat", -1))
                host_seat = snapshot.get("host_seat")
                is_host = seat == host_seat
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if is_host and LOBBY_MINUS_RECT.collidepoint(event.pos) and target > min_allowed:
                        network.send({"type": "set_player_count", "player_count": target - 1})
                    elif is_host and LOBBY_PLUS_RECT.collidepoint(event.pos) and target < max_players:
                        network.send({"type": "set_player_count", "player_count": target + 1})
                    elif LOBBY_START_RECT.collidepoint(event.pos):
                        network.send({"type": "start"})
                elif event.type == pygame.KEYDOWN:
                    if is_host and event.key == pygame.K_LEFT and target > min_allowed:
                        network.send({"type": "set_player_count", "player_count": target - 1})
                    elif is_host and event.key == pygame.K_RIGHT and target < max_players:
                        network.send({"type": "set_player_count", "player_count": target + 1})
                    elif event.key == pygame.K_RETURN:
                        network.send({"type": "start"})

            elif phase == "game":
                game = snapshot.get("game") or {}
                seat = int(snapshot.get("seat", -1))
                hand = [card_from_dict(x) for x in game.get("hand", [])]
                pending = game.get("pending_selection")

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    index = clicked_card(event.pos, hand_rect_cache)
                    if index is not None and index < len(hand):
                        cid = card_id(hand[index])
                        bright = bright_card_ids(hand, selected_ids, game, seat)
                        if cid in selected_ids:
                            selected_ids.remove(cid)
                        elif cid in bright:
                            if isinstance(pending, dict) and pending.get("source_player") == seat:
                                required = int(pending.get("count", 0))
                                if len(selected_ids) < required:
                                    selected_ids.add(cid)
                            else:
                                selected_ids.add(cid)
                    elif PLAY_RECT.collidepoint(event.pos):
                        if isinstance(pending, dict) and pending.get("source_player") == seat:
                            network.send({"type": "effect_select", "cards": sorted(selected_ids)})
                        else:
                            network.send({"type": "play", "cards": sorted(selected_ids)})
                        selected_ids.clear()
                    elif PASS_RECT.collidepoint(event.pos):
                        network.send({"type": "pass"})
                        selected_ids.clear()

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        selected_ids.clear()
                    elif event.key == pygame.K_RETURN:
                        if isinstance(pending, dict) and pending.get("source_player") == seat:
                            network.send({"type": "effect_select", "cards": sorted(selected_ids)})
                        else:
                            network.send({"type": "play", "cards": sorted(selected_ids)})
                        selected_ids.clear()
                    elif event.key == pygame.K_p:
                        network.send({"type": "pass"})
                        selected_ids.clear()

            elif phase == "result":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if NEXT_ROUND_RECT.collidepoint(event.pos):
                        network.send({"type": "next_round"})
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    network.send({"type": "next_round"})

        if snapshot is None:
            draw_connect(screen, fonts, host_value, name_value, active_field, status)
        elif phase == "lobby":
            draw_lobby(screen, fonts, snapshot)
            hand_rect_cache = []
        elif phase in ("game", "paused"):
            hand_rect_cache = draw_game(screen, fonts, snapshot, selected_ids)
            if phase == "paused":
                overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 130))
                screen.blit(overlay, (0, 0))
                draw_text(screen, "接続が切れたため停止しています", fonts.heading, RED, (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        elif phase == "result":
            draw_result(screen, fonts, snapshot)
            hand_rect_cache = []

        pygame.display.flip()
        clock.tick(FPS)

    network.close()
    pygame.quit()


if __name__ == "__main__":
    main()
