from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(slots=True)
class RuleSettings:
    joker: bool = True
    eight_cut: bool = True
    revolution: bool = True
    spade_three_return: bool = True
    suit_lock: bool = True
    staircase: bool = True
    five_skip: bool = False
    seven_pass: bool = False
    ten_discard: bool = False
    eleven_back: bool = False
    forbidden_finish: bool = True
    card_exchange: bool = False
    capital_fall: bool = False

    def copy(self) -> "RuleSettings":
        return RuleSettings(**self.to_dict())

    def to_dict(self) -> dict[str, bool]:
        return {field.name: bool(getattr(self, field.name)) for field in fields(self)}

    @classmethod
    def from_preset(cls, name: str) -> "RuleSettings":
        if name == "simple":
            return cls(
                joker=False,
                eight_cut=False,
                revolution=False,
                spade_three_return=False,
                suit_lock=False,
                staircase=False,
                five_skip=False,
                seven_pass=False,
                ten_discard=False,
                eleven_back=False,
                forbidden_finish=False,
                card_exchange=False,
                capital_fall=False,
            )
        if name == "standard":
            return cls()
        if name == "party":
            return cls(**{field.name: True for field in fields(cls)})
        raise ValueError(f"不明なプリセットです: {name}")


@dataclass(frozen=True, slots=True)
class RuleInfo:
    key: str
    label: str
    description: str


RULE_INFOS: tuple[RuleInfo, ...] = (
    RuleInfo("joker", "ジョーカー", "1枚・組札のワイルドカード。単体は最強"),
    RuleInfo("eight_cut", "8切り", "8を含む手を出すと場が流れる"),
    RuleInfo("revolution", "革命", "4枚組または4枚以上の階段で強さが逆転"),
    RuleInfo("spade_three_return", "スペード3返し", "単体ジョーカーに♠3を出すと場が流れる"),
    RuleInfo("suit_lock", "縛り", "同じスート構成が2回続くと、そのスートに固定"),
    RuleInfo("staircase", "階段", "同じスートの連番を3枚以上まとめて出せる"),
    RuleInfo("five_skip", "5飛び", "出した5の枚数だけ次の人を飛ばす"),
    RuleInfo("seven_pass", "7渡し", "出した7の枚数だけ次の人へカードを渡す"),
    RuleInfo("ten_discard", "10捨て", "出した10の枚数だけ手札を捨てる"),
    RuleInfo("eleven_back", "11バック", "Jが出た場だけ強さが一時的に逆転"),
    RuleInfo("forbidden_finish", "禁止上がり", "8切り有効時の8・ジョーカーでの上がりを禁止"),
    RuleInfo("card_exchange", "カード交換", "2戦目以降、階級に応じてカードを交換"),
    RuleInfo("capital_fall", "都落ち", "前回の大富豪が1位を逃すと大貧民になる"),
)
