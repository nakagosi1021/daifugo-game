from __future__ import annotations

from itertools import combinations
from typing import Any

from card import Card
from game_engine import GameState, validate_play


def card_to_dict(card: Card) -> dict[str, str]:
    return {"suit": card.suit, "rank": card.rank}


def card_from_dict(data: dict[str, Any]) -> Card:
    return Card(str(data["suit"]), str(data["rank"]))


def card_id(card: Card) -> str:
    return f"{card.suit}|{card.rank}"


def cards_from_ids(hand: list[Card], ids: list[str]) -> list[Card] | None:
    by_id = {card_id(card): card for card in hand}
    cards: list[Card] = []
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            return None
        seen.add(item)
        card = by_id.get(item)
        if card is None:
            return None
        cards.append(card)
    return cards


def legal_plays_for(state: GameState, player_index: int) -> list[list[str]]:
    """手札が少ない大富豪向けに全部分集合を調べ、合法手を返す。"""
    if (
        state.game_over
        or state.current_player != player_index
        or state.pending_selection is not None
        or state.pending_display is not None
    ):
        return []

    hand = state.hands[player_index]
    legal: list[list[str]] = []
    # 6人なら通常8〜9枚。最大でも2^14程度なので十分軽い。
    for count in range(1, len(hand) + 1):
        for combo in combinations(hand, count):
            valid, _, _ = validate_play(state, player_index, list(combo))
            if valid:
                legal.append([card_id(card) for card in combo])
    return legal
