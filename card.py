from __future__ import annotations

from dataclasses import dataclass

RANKS: tuple[str, ...] = (
    "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"
)
SUITS: tuple[str, ...] = ("♠", "♥", "♦", "♣")
JOKER_RANK = "JOKER"
JOKER_SUIT = "JOKER"


@dataclass(frozen=True, slots=True)
class Card:
    """トランプ1枚を表す。"""

    suit: str
    rank: str

    @property
    def is_joker(self) -> bool:
        return self.rank == JOKER_RANK

    @property
    def rank_value(self) -> int:
        """3=0 ... 2=12、ジョーカー=13。"""
        if self.is_joker:
            return len(RANKS)
        return RANKS.index(self.rank)

    def __str__(self) -> str:
        if self.is_joker:
            return "JOKER"
        return f"{self.suit}{self.rank}"


def card_sort_key(card: Card) -> tuple[int, int]:
    """画面表示用。3→2→JOKER、同じ数字はスート順。"""
    suit_index = len(SUITS) if card.is_joker else SUITS.index(card.suit)
    return card.rank_value, suit_index
