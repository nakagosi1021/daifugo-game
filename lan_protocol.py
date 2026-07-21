from __future__ import annotations

import json
import socket
import threading
from typing import Any

MAX_MESSAGE_BYTES = 1_000_000


def encode_message(message: dict[str, Any]) -> bytes:
    return (
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def send_message(
    sock: socket.socket,
    message: dict[str, Any],
    lock: threading.Lock | None = None,
) -> None:
    payload = encode_message(message)
    if lock is None:
        sock.sendall(payload)
        return
    with lock:
        sock.sendall(payload)


def receive_messages(sock: socket.socket):
    """改行区切りJSONを順次返す。"""
    buffer = bytearray()
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            return
        buffer.extend(chunk)
        if len(buffer) > MAX_MESSAGE_BYTES:
            raise ValueError("受信メッセージが大きすぎます。")

        while True:
            newline_index = buffer.find(b"\n")
            if newline_index < 0:
                break
            raw = bytes(buffer[:newline_index])
            del buffer[: newline_index + 1]
            if not raw:
                continue
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                yield data
