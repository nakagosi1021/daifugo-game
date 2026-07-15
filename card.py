from dataclasses import dataclass


# 大富豪で弱い順に並べています
RANKS = (
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
    "A",
    "2",
)

SUITS = ("♠", "♥", "♦", "♣")


@dataclass(frozen=True)
class Card:
    """トランプ1枚を表すクラス。"""

    suit: str
    rank: str

    @property
    def strength(self) -> int:
        """カードの強さを数値で返す。3が最弱、2が最強。"""
        return RANKS.index(self.rank)

    def __str__(self) -> str:
        """カードを「♠3」のような文字で表示する。"""
        return f"{self.suit}{self.rank}"