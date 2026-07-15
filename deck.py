import random

from card import Card, RANKS, SUITS


class Deck:
    """トランプの山札を管理するクラス。"""

    def __init__(self) -> None:
        self.cards = [
            Card(suit=suit, rank=rank)
            for suit in SUITS
            for rank in RANKS
        ]

    def shuffle(self) -> None:
        """山札をランダムに並べ替える。"""
        random.shuffle(self.cards)

    def deal(self, number_of_players: int = 4) -> list[list[Card]]:
        """カードを指定した人数に1枚ずつ配る。"""
        if number_of_players <= 0:
            raise ValueError("プレイヤー数は1人以上にしてください。")

        hands: list[list[Card]] = [
            [] for _ in range(number_of_players)
        ]

        for index, card in enumerate(self.cards):
            player_index = index % number_of_players
            hands[player_index].append(card)

        # 各プレイヤーの手札を、弱いカードから順に並べる
        for hand in hands:
            hand.sort(
                key=lambda card: (
                    card.strength,
                    SUITS.index(card.suit),
                )
            )

        # 配り終わったので山札を空にする
        self.cards.clear()

        return hands