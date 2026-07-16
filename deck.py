from __future__ import annotations

import random

from card import Card, JOKER_RANK, JOKER_SUIT, RANKS, SUITS, card_sort_key


class Deck:
    def __init__(self, include_joker: bool) -> None:
        self.cards = [Card(suit, rank) for suit in SUITS for rank in RANKS]
        if include_joker:
            self.cards.append(Card(JOKER_SUIT, JOKER_RANK))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def deal(self, player_count: int = 4) -> list[list[Card]]:
        if player_count < 2:
            raise ValueError("プレイヤー数は2人以上にしてください。")
        hands: list[list[Card]] = [[] for _ in range(player_count)]
        for index, card in enumerate(self.cards):
            hands[index % player_count].append(card)
        for hand in hands:
            hand.sort(key=card_sort_key)
        self.cards.clear()
        return hands
