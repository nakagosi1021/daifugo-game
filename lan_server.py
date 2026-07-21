from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import queue
import socket
import threading
import time
from pathlib import Path
from typing import Any

from app_settings import load_settings
from game_engine import (
    GameSession,
    GameState,
    confirm_pending_selection,
    create_game,
    pass_turn,
    play_cards,
    process_cpu_turn,
    rank_titles_for,
    resolve_pending_display,
    table_description,
)
import game_engine
from lan_common import card_id, card_to_dict, cards_from_ids, legal_plays_for
from lan_protocol import receive_messages, send_message

MIN_PLAYERS = 2
MAX_PLAYERS = 6
DEFAULT_PLAYER_COUNT = 6
DEFAULT_PORT = 50000
CPU_TURN_DELAY_MS = 650
SETTINGS_PATH = Path(__file__).with_name("settings.json")


@dataclass(slots=True)
class ClientPeer:
    seat: int
    name: str
    sock: socket.socket
    address: tuple[str, int]
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    connected: bool = True

    def send(self, message: dict[str, Any]) -> None:
        send_message(self.sock, message, self.send_lock)

    def close(self) -> None:
        self.connected = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class LanGameServer:
    def __init__(self, host: str, port: int, player_count: int) -> None:
        self.host = host
        self.port = port
        self.target_player_count = max(MIN_PLAYERS, min(MAX_PLAYERS, player_count))
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen(12)
        self.listener.settimeout(0.5)

        self.clients: dict[int, ClientPeer] = {}
        self.clients_lock = threading.Lock()
        self.events: queue.Queue[tuple[str, int, dict[str, Any] | None]] = queue.Queue()
        self.running = True
        self.phase = "lobby"  # lobby / game / result / paused
        self.state: GameState | None = None
        self.session: GameSession | None = None
        self.host_seat: int | None = None
        self.last_broadcast_at = 0.0

    def available_seat(self) -> int | None:
        with self.clients_lock:
            for seat in range(MAX_PLAYERS):
                if seat not in self.clients:
                    return seat
        return None

    def connected_seats(self) -> list[int]:
        with self.clients_lock:
            return sorted(
                seat for seat, peer in self.clients.items() if peer.connected
            )

    def min_player_count_for_lobby(self) -> int:
        connected = self.connected_seats()
        if not connected:
            return MIN_PLAYERS
        return max(MIN_PLAYERS, max(connected) + 1)

    def set_target_player_count(self, count: int) -> None:
        if self.phase != "lobby":
            return
        minimum = self.min_player_count_for_lobby()
        self.target_player_count = max(minimum, min(MAX_PLAYERS, count))
        self.broadcast_all(force=True)

    def player_names(self, player_count: int | None = None) -> list[str]:
        count = player_count if player_count is not None else MAX_PLAYERS
        with self.clients_lock:
            names: list[str] = []
            cpu_number = 1
            for seat in range(count):
                if seat in self.clients:
                    names.append(self.clients[seat].name)
                else:
                    names.append(f"CPU{cpu_number}")
                    cpu_number += 1
            return names

    def accept_loop(self) -> None:
        while self.running:
            try:
                sock, address = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return

            thread = threading.Thread(
                target=self.handle_new_connection,
                args=(sock, address),
                daemon=True,
            )
            thread.start()

    def handle_new_connection(
        self,
        sock: socket.socket,
        address: tuple[str, int],
    ) -> None:
        seat = -1
        try:
            sock.settimeout(10.0)
            iterator = receive_messages(sock)
            first = next(iterator, None)
            if first is None or first.get("type") != "join":
                send_message(sock, {"type": "error", "message": "参加要求が不正です。"})
                sock.close()
                return

            name = str(first.get("name", "")).strip()[:16]
            if not name:
                name = "ゲスト"

            with self.clients_lock:
                if self.phase != "lobby":
                    send_message(sock, {"type": "error", "message": "ゲーム開始後は参加できません。"})
                    sock.close()
                    return

                seat = next(
                    (i for i in range(MAX_PLAYERS) if i not in self.clients),
                    -1,
                )
                if seat < 0:
                    send_message(sock, {"type": "error", "message": "部屋は満員です。"})
                    sock.close()
                    return

                peer = ClientPeer(seat, name, sock, address)
                self.clients[seat] = peer
                self.host_seat = min(self.clients)
                if seat >= self.target_player_count:
                    self.target_player_count = seat + 1

            sock.settimeout(None)
            peer.send(
                {
                    "type": "welcome",
                    "seat": seat,
                    "player_count": self.target_player_count,
                    "max_player_count": MAX_PLAYERS,
                }
            )
            print(f"[接続] 席{seat + 1}: {name} ({address[0]})")
            self.broadcast_all(force=True)

            for message in iterator:
                self.events.put(("message", seat, message))
        except (OSError, ValueError, StopIteration) as exc:
            print(f"[通信終了] {address}: {exc}")
        finally:
            self.events.put(("disconnect", seat, None))

    def remove_client(self, seat: int) -> None:
        if seat < 0:
            return
        with self.clients_lock:
            peer = self.clients.pop(seat, None)
            if peer is None:
                return
            peer.close()
            self.host_seat = min(self.clients) if self.clients else None

        print(f"[切断] 席{seat + 1}: {peer.name}")
        if self.phase == "lobby":
            self.target_player_count = max(
                self.min_player_count_for_lobby(),
                min(MAX_PLAYERS, self.target_player_count),
            )
            self.broadcast_all(force=True)
        else:
            self.phase = "paused"
            if self.state is not None:
                self.state.message = (
                    f"{peer.name}が切断しました。サーバーを起動し直してください。"
                )
            self.broadcast_all(force=True)

    def can_start_game(self) -> bool:
        connected = self.connected_seats()
        return (
            self.phase == "lobby"
            and self.host_seat is not None
            and MIN_PLAYERS <= self.target_player_count <= MAX_PLAYERS
            and all(seat < self.target_player_count for seat in connected)
        )

    def start_game(self) -> None:
        if not self.can_start_game():
            return

        settings = load_settings(SETTINGS_PATH)
        player_count = self.target_player_count
        names = self.player_names(player_count)
        game_engine.PLAYER_NAMES = tuple(names)
        human_players = set(self.connected_seats())
        self.session = GameSession(
            rules=settings.rules.copy(),
            player_count=player_count,
            cpu_difficulty=settings.cpu_difficulty,
            demo_mode=False,
            human_players=human_players,
        )
        self.state = create_game(self.session, self.now_ms())
        self.phase = "game"
        cpu_count = player_count - len(human_players)
        print(f"[開始] {player_count}人対戦を開始しました（CPU {cpu_count}人）")
        self.broadcast_all(force=True)

    def next_round(self) -> None:
        if self.session is None:
            return
        self.session.round_number += 1
        self.state = create_game(self.session, self.now_ms())
        self.phase = "game"
        print(f"[次ラウンド] 第{self.session.round_number}戦")
        self.broadcast_all(force=True)

    @staticmethod
    def now_ms() -> int:
        return int(time.monotonic() * 1000)

    def handle_action(self, seat: int, message: dict[str, Any]) -> None:
        action = message.get("type")
        if action == "set_player_count":
            if self.phase == "lobby" and seat == self.host_seat:
                try:
                    self.set_target_player_count(int(message.get("player_count", 0)))
                except (TypeError, ValueError):
                    pass
            return

        if action == "start":
            if self.phase == "lobby" and seat == self.host_seat:
                self.start_game()
            return

        if action == "next_round":
            if self.phase == "result" and seat == self.host_seat:
                self.next_round()
            return

        state = self.state
        if self.phase != "game" or state is None:
            return
        if seat not in state.session.human_players:
            return

        if action == "play":
            ids = message.get("cards", [])
            if not isinstance(ids, list):
                return
            cards = cards_from_ids(state.hands[seat], [str(x) for x in ids])
            if cards is None:
                state.message = "選択されたカードが手札にありません。"
            else:
                success, error = play_cards(state, seat, cards)
                if not success:
                    state.message = error
                else:
                    state.turn_started_at = self.now_ms()
            self.broadcast_all(force=True)
            return

        if action == "pass":
            success, error = pass_turn(state, seat)
            if not success:
                state.message = error
            else:
                state.turn_started_at = self.now_ms()
            self.broadcast_all(force=True)
            return

        if action == "effect_select":
            ids = message.get("cards", [])
            if not isinstance(ids, list):
                return
            cards = cards_from_ids(state.hands[seat], [str(x) for x in ids])
            if cards is None:
                state.message = "選択されたカードが手札にありません。"
            else:
                index_by_id = {
                    card_id(card): index
                    for index, card in enumerate(state.hands[seat])
                }
                indices = {index_by_id[card_id(card)] for card in cards}
                success, error = confirm_pending_selection(
                    state,
                    indices,
                    player_index=seat,
                )
                if not success:
                    state.message = error
                else:
                    state.turn_started_at = self.now_ms()
            self.broadcast_all(force=True)

    def update_game(self) -> None:
        if self.phase != "game" or self.state is None:
            return

        state = self.state
        pending = state.pending_display
        now = self.now_ms()
        if pending is not None:
            if pending.started_at is None:
                pending.started_at = now
                self.broadcast_all(force=True)
            elif now - pending.started_at >= pending.duration_ms:
                resolve_pending_display(state)
                state.turn_started_at = now
                self.broadcast_all(force=True)
            return

        if (
            not state.game_over
            and state.pending_selection is None
            and state.current_player not in state.session.human_players
            and now - state.turn_started_at >= CPU_TURN_DELAY_MS
        ):
            process_cpu_turn(state)
            state.turn_started_at = now
            self.broadcast_all(force=True)

        if state.game_over and state.pending_display is None:
            self.phase = "result"
            self.broadcast_all(force=True)

    def rule_dict(self) -> dict[str, bool]:
        if self.session is None:
            settings = load_settings(SETTINGS_PATH)
            return settings.rules.to_dict()
        return self.session.rules.to_dict()

    def snapshot_for(self, seat: int) -> dict[str, Any]:
        names = self.player_names(
            self.target_player_count if self.state is not None else MAX_PLAYERS
        )
        connected = self.connected_seats()
        payload: dict[str, Any] = {
            "type": "state",
            "phase": self.phase,
            "seat": seat,
            "host_seat": self.host_seat,
            "player_count": self.target_player_count,
            "max_player_count": MAX_PLAYERS,
            "min_player_count": MIN_PLAYERS,
            "names": names,
            "connected": connected,
            "human_players": connected,
            "rules": self.rule_dict(),
            "can_start": self.can_start_game(),
        }

        if self.state is None:
            payload["game"] = None
            return payload

        state = self.state
        pending_selection = None
        if state.pending_selection is not None:
            pending_selection = {
                "action": state.pending_selection.action,
                "source_player": state.pending_selection.source_player,
                "target_player": state.pending_selection.target_player,
                "count": state.pending_selection.count,
                "prompt": state.pending_selection.prompt,
            }

        pending_display = None
        if state.pending_display is not None:
            pending_display = {
                "effect": state.pending_display.effect,
                "player_index": state.pending_display.player_index,
            }

        legal_plays: list[list[str]] = []
        if state.current_player == seat and seat in state.session.human_players:
            legal_plays = legal_plays_for(state, seat)

        payload["game"] = {
            "hand": [card_to_dict(card) for card in state.hands[seat]],
            "table_cards": [card_to_dict(card) for card in state.table_cards],
            "card_counts": [len(hand) for hand in state.hands],
            "current_player": state.current_player,
            "passed_players": sorted(state.passed_players),
            "rankings": state.rankings.copy(),
            "message": state.message,
            "revolution": state.revolution,
            "eleven_back": state.eleven_back,
            "locked_suits": list(state.locked_suits) if state.locked_suits else None,
            "first_turn": state.first_turn,
            "game_over": state.game_over,
            "round_number": state.session.round_number,
            "pending_selection": pending_selection,
            "pending_display": pending_display,
            "legal_plays": legal_plays,
            "table_description": table_description(state),
            "rank_titles": list(rank_titles_for(state.session.player_count)),
        }
        return payload

    def broadcast_all(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_broadcast_at < 0.1:
            return
        self.last_broadcast_at = now

        with self.clients_lock:
            peers = list(self.clients.values())

        for peer in peers:
            if not peer.connected:
                continue
            try:
                peer.send(self.snapshot_for(peer.seat))
            except OSError:
                self.events.put(("disconnect", peer.seat, None))

    def run(self) -> None:
        print(f"LAN大富豪サーバーを開始しました: 0.0.0.0:{self.port}")
        print("ホストPCでも lan_client.py を起動して参加してください。")
        accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
        accept_thread.start()

        try:
            while self.running:
                try:
                    event_type, seat, payload = self.events.get(timeout=0.03)
                except queue.Empty:
                    event_type = ""
                    seat = -1
                    payload = None

                if event_type == "message" and payload is not None:
                    self.handle_action(seat, payload)
                elif event_type == "disconnect":
                    self.remove_client(seat)

                self.update_game()
                self.broadcast_all()
        except KeyboardInterrupt:
            print("\nサーバーを終了します。")
        finally:
            self.running = False
            try:
                self.listener.close()
            except OSError:
                pass
            with self.clients_lock:
                peers = list(self.clients.values())
                self.clients.clear()
            for peer in peers:
                peer.close()


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN大富豪サーバー")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--players", type=int, default=DEFAULT_PLAYER_COUNT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("接続に使う候補IP:")
    addresses = local_ipv4_addresses()
    if addresses:
        for address in addresses:
            print(f"  {address}")
    else:
        print("  ipconfig でIPv4アドレスを確認してください。")
    server = LanGameServer(args.host, args.port, args.players)
    server.run()


if __name__ == "__main__":
    main()
