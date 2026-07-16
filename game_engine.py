from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import random

from card import Card, RANKS, SUITS, card_sort_key
from deck import Deck
from rules import RuleSettings

PLAYER_NAMES: tuple[str, ...] = ("あなた", "CPU1", "CPU2", "CPU3")
RANK_TITLES: tuple[str, ...] = ("大富豪", "富豪", "貧民", "大貧民")


@dataclass(frozen=True, slots=True)
class PlayPattern:
    kind: str  # group / straight
    count: int
    strength: int
    cards: tuple[Card, ...]
    primary_rank: str | None
    suit_signature: tuple[str, ...] | None
    actual_suits: tuple[str, ...]
    joker_count: int
    straight_ranks: tuple[int, ...] = ()

    @property
    def is_single_joker(self) -> bool:
        return self.count == 1 and self.joker_count == 1

    def represents_rank(self, rank: str) -> bool:
        if self.kind == "group":
            return self.primary_rank == rank
        rank_value = RANKS.index(rank)
        return rank_value in self.straight_ranks

    def effect_count(self, rank: str) -> int:
        """ローカルルール用。組札ではジョーカーもその数字として数える。"""
        if self.kind == "group":
            return self.count if self.primary_rank == rank else 0
        rank_value = RANKS.index(rank)
        return 1 if rank_value in self.straight_ranks else 0


@dataclass(slots=True)
class PendingSelection:
    action: str  # give / discard
    source_player: int
    target_player: int | None
    count: int
    prompt: str


@dataclass(slots=True)
class PendingDisplay:
    effect: str  # eight_cut / spade_three
    player_index: int
    duration_ms: int = 1800
    started_at: int | None = None


@dataclass(slots=True)
class PostPlayContext:
    player_index: int
    pattern: PlayPattern
    skip_count: int
    seven_count: int
    ten_count: int
    clear_effect: str | None
    forbidden_finish: bool = False
    messages: list[str] = field(default_factory=list)
    next_effect_index: int = 0


@dataclass(slots=True)
class GameSession:
    rules: RuleSettings
    round_number: int = 1
    previous_rankings: list[int] | None = None

    def reset(self, rules: RuleSettings | None = None) -> None:
        if rules is not None:
            self.rules = rules.copy()
        self.round_number = 1
        self.previous_rankings = None


@dataclass(slots=True)
class GameState:
    session: GameSession
    hands: list[list[Card]]
    current_player: int
    selected_indices: set[int] = field(default_factory=set)
    table_cards: list[Card] = field(default_factory=list)
    table_pattern: PlayPattern | None = None
    passed_players: set[int] = field(default_factory=set)
    rankings: list[int] = field(default_factory=list)
    last_played_player: int | None = None
    first_turn: bool = True
    revolution: bool = False
    eleven_back: bool = False
    locked_suits: tuple[str, ...] | None = None
    last_suit_signature: tuple[str, ...] | None = None
    message: str = ""
    game_over: bool = False
    turn_started_at: int = 0
    pending_selection: PendingSelection | None = None
    pending_display: PendingDisplay | None = None
    pending_post_play: PostPlayContext | None = None
    penalty_players: list[int] = field(default_factory=list)

    @property
    def rules(self) -> RuleSettings:
        return self.session.rules

    @property
    def effective_reverse(self) -> bool:
        return self.revolution ^ self.eleven_back


# ---------------------------------------------------------------------------
# カード構成・手の解析
# ---------------------------------------------------------------------------


def _group_pattern(cards: list[Card], rules: RuleSettings) -> PlayPattern | None:
    if not cards or len(cards) > 4:
        return None

    joker_cards = [card for card in cards if card.is_joker]
    normal_cards = [card for card in cards if not card.is_joker]

    if joker_cards and not rules.joker:
        return None
    if len(joker_cards) > 1:
        return None

    if len(cards) == 1:
        card = cards[0]
        if card.is_joker:
            return PlayPattern(
                kind="group",
                count=1,
                strength=len(RANKS),
                cards=tuple(cards),
                primary_rank=None,
                suit_signature=None,
                actual_suits=(),
                joker_count=1,
            )
        return PlayPattern(
            kind="group",
            count=1,
            strength=card.rank_value,
            cards=tuple(cards),
            primary_rank=card.rank,
            suit_signature=(card.suit,),
            actual_suits=(card.suit,),
            joker_count=0,
        )

    if not normal_cards:
        return None

    ranks = {card.rank for card in normal_cards}
    if len(ranks) != 1:
        return None

    primary_rank = normal_cards[0].rank
    actual_suits = tuple(sorted((card.suit for card in normal_cards), key=SUITS.index))
    suit_signature = None if joker_cards else actual_suits

    return PlayPattern(
        kind="group",
        count=len(cards),
        strength=normal_cards[0].rank_value,
        cards=tuple(cards),
        primary_rank=primary_rank,
        suit_signature=suit_signature,
        actual_suits=actual_suits,
        joker_count=len(joker_cards),
    )


def _straight_pattern(cards: list[Card], rules: RuleSettings) -> PlayPattern | None:
    if not rules.staircase or len(cards) < 3:
        return None
    if any(card.is_joker for card in cards):
        # ジョーカーを階段の穴埋めに使うと候補が曖昧になるため、本作では不使用。
        return None

    suits = {card.suit for card in cards}
    if len(suits) != 1:
        return None

    values = sorted(card.rank_value for card in cards)
    if values[-1] >= RANKS.index("2"):
        # 2を含む階段は不採用。
        return None
    if len(set(values)) != len(values):
        return None
    if any(right - left != 1 for left, right in zip(values, values[1:])):
        return None

    suit = cards[0].suit
    return PlayPattern(
        kind="straight",
        count=len(cards),
        strength=values[-1],
        cards=tuple(sorted(cards, key=card_sort_key)),
        primary_rank=None,
        suit_signature=(suit,),
        actual_suits=(suit,),
        joker_count=0,
        straight_ranks=tuple(values),
    )


def analyze_play(cards: list[Card], rules: RuleSettings) -> PlayPattern | None:
    if not cards:
        return None
    group = _group_pattern(cards, rules)
    if group is not None:
        return group
    return _straight_pattern(cards, rules)


def _satisfies_lock(pattern: PlayPattern, locked_suits: tuple[str, ...]) -> bool:
    if pattern.joker_count == 0:
        return pattern.suit_signature == locked_suits

    if pattern.kind != "group":
        return False

    # ジョーカーは不足しているスートの代わりになれる。
    actual = list(pattern.actual_suits)
    required = list(locked_suits)
    for suit in actual:
        if suit not in required:
            return False
        required.remove(suit)
    return len(required) == pattern.joker_count


def _normal_pattern_stronger(candidate: PlayPattern, table: PlayPattern, reverse: bool) -> bool:
    if candidate.is_single_joker:
        return not table.is_single_joker
    if table.is_single_joker:
        return False
    if reverse:
        return candidate.strength < table.strength
    return candidate.strength > table.strength


def is_spade_three_return(
    pattern: PlayPattern,
    table_pattern: PlayPattern | None,
    rules: RuleSettings,
) -> bool:
    if not rules.spade_three_return or table_pattern is None:
        return False
    if not table_pattern.is_single_joker or pattern.count != 1:
        return False
    card = pattern.cards[0]
    return not card.is_joker and card.suit == "♠" and card.rank == "3"


def validate_play(
    state: GameState,
    player_index: int,
    cards: list[Card],
) -> tuple[bool, str, PlayPattern | None]:
    if state.game_over:
        return False, "ゲームは終了しています", None
    if player_index != state.current_player:
        return False, "現在の手番ではありません", None
    if state.pending_selection or state.pending_display:
        return False, "効果の処理中です", None

    pattern = analyze_play(cards, state.rules)
    if pattern is None:
        return False, "同じ数字の組、または同じスートの連番を選んでください", None

    if state.first_turn:
        has_diamond_three = any(
            not card.is_joker and card.suit == "♦" and card.rank == "3"
            for card in cards
        )
        if not has_diamond_three:
            return False, "最初は♦3を含む手を出してください", None

    if state.locked_suits is not None and not _satisfies_lock(pattern, state.locked_suits):
        locked_text = "・".join(state.locked_suits)
        return False, f"縛り中です。スート構成を {locked_text} に合わせてください", None

    table = state.table_pattern
    if table is not None:
        if pattern.kind != table.kind or pattern.count != table.count:
            if table.kind == "straight":
                return False, f"場と同じ{table.count}枚の階段を出してください", None
            return False, f"場と同じ{table.count}枚組を出してください", None

        if table.is_single_joker:
            if not is_spade_three_return(pattern, table, state.rules):
                return False, "ジョーカーには♠3だけを出せます", None
        elif not _normal_pattern_stronger(pattern, table, state.effective_reverse):
            direction = "小さい" if state.effective_reverse else "大きい"
            return False, f"場より数字の{direction}手を出してください", None

    return True, "", pattern


def is_forbidden_finish(state: GameState, pattern: PlayPattern, remaining_count: int) -> bool:
    """禁止上がりはプレイを拒否せず、上がった人を最下位側へ送る。"""
    if not state.rules.forbidden_finish or remaining_count != 0:
        return False
    weakest_forbidden = "3" if state.effective_reverse else "2"
    return (
        pattern.represents_rank(weakest_forbidden)
        or (state.rules.eight_cut and pattern.represents_rank("8"))
        or any(card.is_joker for card in pattern.cards)
    )


# ---------------------------------------------------------------------------
# ゲーム準備・連戦ルール
# ---------------------------------------------------------------------------


def _strongest_cards(hand: list[Card], count: int) -> list[Card]:
    return sorted(hand, key=card_sort_key, reverse=True)[:count]


def _weakest_cards(hand: list[Card], count: int) -> list[Card]:
    return sorted(hand, key=card_sort_key)[:count]


def _transfer_cards(hands: list[list[Card]], source: int, target: int, cards: list[Card]) -> None:
    for card in cards:
        hands[source].remove(card)
        hands[target].append(card)
    hands[source].sort(key=card_sort_key)
    hands[target].sort(key=card_sort_key)


def apply_automatic_exchange(hands: list[list[Card]], previous_rankings: list[int]) -> list[str]:
    """課題向けに交換を自動化。貧しい側は最強、富裕側は最弱を渡す。"""
    messages: list[str] = []
    daifugo, fugo, hinmin, daihinmin = previous_rankings

    poor_to_rich = _strongest_cards(hands[daihinmin], 2)
    rich_to_poor = _weakest_cards(hands[daifugo], 2)
    _transfer_cards(hands, daihinmin, daifugo, poor_to_rich)
    _transfer_cards(hands, daifugo, daihinmin, rich_to_poor)
    messages.append("大富豪と大貧民が2枚交換")

    poor_to_rich = _strongest_cards(hands[hinmin], 1)
    rich_to_poor = _weakest_cards(hands[fugo], 1)
    _transfer_cards(hands, hinmin, fugo, poor_to_rich)
    _transfer_cards(hands, fugo, hinmin, rich_to_poor)
    messages.append("富豪と貧民が1枚交換")
    return messages


def find_start_player(hands: list[list[Card]]) -> int:
    for player_index, hand in enumerate(hands):
        for card in hand:
            if not card.is_joker and card.suit == "♦" and card.rank == "3":
                return player_index
    raise RuntimeError("♦3を持つプレイヤーが見つかりません。")


def create_game(session: GameSession, now_ms: int = 0) -> GameState:
    deck = Deck(include_joker=session.rules.joker)
    deck.shuffle()
    hands = deck.deal(4)

    exchange_messages: list[str] = []
    if (
        session.rules.card_exchange
        and session.previous_rankings is not None
        and len(session.previous_rankings) == 4
    ):
        exchange_messages = apply_automatic_exchange(hands, session.previous_rankings)

    current_player = find_start_player(hands)
    prefix = "／".join(exchange_messages)
    if prefix:
        prefix += "。"
    message = (
        f"{prefix}{PLAYER_NAMES[current_player]}が♦3を持っています。ここから開始します"
    )

    return GameState(
        session=session,
        hands=hands,
        current_player=current_player,
        message=message,
        turn_started_at=now_ms,
    )


# ---------------------------------------------------------------------------
# ターン・場・順位
# ---------------------------------------------------------------------------


def active_players(state: GameState) -> list[int]:
    return [
        index
        for index, hand in enumerate(state.hands)
        if hand and index not in state.penalty_players
    ]


def next_player(
    state: GameState,
    from_player: int,
    steps: int = 1,
    ignore_passed: bool = False,
) -> int | None:
    if steps < 1:
        steps = 1
    found = 0
    for offset in range(1, 33):
        candidate = (from_player + offset) % len(state.hands)
        if not state.hands[candidate] or candidate in state.penalty_players:
            continue
        if not ignore_passed and candidate in state.passed_players:
            continue
        found += 1
        if found == steps:
            return candidate
    return None


def clear_table(state: GameState) -> None:
    state.table_cards.clear()
    state.table_pattern = None
    state.passed_players.clear()
    state.locked_suits = None
    state.last_suit_signature = None
    state.eleven_back = False
    state.last_played_player = None


def _complete_ranking_if_needed(state: GameState) -> None:
    remaining = [player for player in active_players(state) if player not in state.rankings]
    if len(remaining) <= 1:
        for player in remaining:
            state.rankings.append(player)
        for player in state.penalty_players:
            if player not in state.rankings:
                state.rankings.append(player)
        # 念のため未登録者を埋める。
        for player in range(len(state.hands)):
            if player not in state.rankings:
                state.rankings.append(player)
        state.game_over = len(state.rankings) == len(state.hands)
        if state.game_over:
            state.session.previous_rankings = state.rankings.copy()


def _register_finish_and_capital_fall(state: GameState, player_index: int) -> list[str]:
    messages: list[str] = []
    if state.hands[player_index] or player_index in state.rankings:
        return messages

    state.rankings.append(player_index)
    place = len(state.rankings)
    messages.append(f"{PLAYER_NAMES[player_index]}が{place}位で上がり")

    if (
        place == 1
        and state.rules.capital_fall
        and state.session.previous_rankings is not None
    ):
        previous_daifugo = state.session.previous_rankings[0]
        if (
            previous_daifugo != player_index
            and previous_daifugo not in state.rankings
            and previous_daifugo not in state.penalty_players
        ):
            # 都落ちは絶対的な最下位なので、ペナルティ列の最後へ。
            state.penalty_players.append(previous_daifugo)
            state.hands[previous_daifugo].clear()
            state.passed_players.discard(previous_daifugo)
            messages.append(f"都落ち：{PLAYER_NAMES[previous_daifugo]}は大貧民")

    _complete_ranking_if_needed(state)
    return messages


def _update_suit_lock(state: GameState, pattern: PlayPattern) -> str | None:
    if not state.rules.suit_lock:
        state.last_suit_signature = pattern.suit_signature
        return None

    signature = pattern.suit_signature
    if state.locked_suits is None:
        if signature is not None and signature == state.last_suit_signature:
            state.locked_suits = signature
            return "縛り成立"
    state.last_suit_signature = signature
    return None


def _revolution_trigger(pattern: PlayPattern) -> bool:
    if pattern.kind == "group":
        return pattern.count == 4
    return pattern.kind == "straight" and pattern.count >= 4


def _format_cards(cards: list[Card] | tuple[Card, ...]) -> str:
    return " ".join(str(card) for card in cards)


# ---------------------------------------------------------------------------
# プレイ後の効果
# ---------------------------------------------------------------------------


def _start_next_pending_effect(state: GameState) -> None:
    context = state.pending_post_play
    if context is None:
        return

    player = context.player_index
    while context.next_effect_index < 2:
        effect_index = context.next_effect_index
        context.next_effect_index += 1

        if effect_index == 0 and context.seven_count > 0 and state.hands[player]:
            count = min(context.seven_count, len(state.hands[player]))
            target = next_player(state, player, ignore_passed=True)
            if target is not None and target != player and count > 0:
                state.pending_selection = PendingSelection(
                    action="give",
                    source_player=player,
                    target_player=target,
                    count=count,
                    prompt=f"7渡し：{PLAYER_NAMES[target]}へ渡すカードを{count}枚選択",
                )
                state.selected_indices.clear()
                state.message = state.pending_selection.prompt
                if player != 0:
                    auto_resolve_pending_selection(state)
                return

        if effect_index == 1 and context.ten_count > 0 and state.hands[player]:
            count = min(context.ten_count, len(state.hands[player]))
            if count > 0:
                state.pending_selection = PendingSelection(
                    action="discard",
                    source_player=player,
                    target_player=None,
                    count=count,
                    prompt=f"10捨て：捨てるカードを{count}枚選択",
                )
                state.selected_indices.clear()
                state.message = state.pending_selection.prompt
                if player != 0:
                    auto_resolve_pending_selection(state)
                return

    _finalize_post_play(state)


def confirm_pending_selection(state: GameState, indices: set[int]) -> tuple[bool, str]:
    pending = state.pending_selection
    context = state.pending_post_play
    if pending is None or context is None:
        return False, "選択処理はありません"
    if pending.source_player != 0:
        return False, "CPUの処理中です"
    if len(indices) != pending.count:
        return False, f"カードを{pending.count}枚選択してください"

    hand = state.hands[pending.source_player]
    if any(index < 0 or index >= len(hand) for index in indices):
        return False, "選択したカードが見つかりません"
    cards = [hand[index] for index in sorted(indices)]
    _apply_pending_cards(state, cards)
    return True, ""


def _apply_pending_cards(state: GameState, cards: list[Card]) -> None:
    pending = state.pending_selection
    context = state.pending_post_play
    if pending is None or context is None:
        return

    source_hand = state.hands[pending.source_player]
    for card in cards:
        source_hand.remove(card)

    if pending.action == "give" and pending.target_player is not None:
        state.hands[pending.target_player].extend(cards)
        state.hands[pending.target_player].sort(key=card_sort_key)
        context.messages.append(
            f"7渡しで{PLAYER_NAMES[pending.target_player]}へ{len(cards)}枚渡した"
        )
    elif pending.action == "discard":
        context.messages.append(f"10捨てで{len(cards)}枚捨てた")

    source_hand.sort(key=card_sort_key)
    state.pending_selection = None
    state.selected_indices.clear()
    _start_next_pending_effect(state)


def auto_resolve_pending_selection(state: GameState) -> None:
    pending = state.pending_selection
    if pending is None:
        return
    hand = state.hands[pending.source_player]
    # CPUは現在の強さで弱いカードを選ぶ。
    cards = sorted(
        hand,
        key=lambda card: (-card.rank_value if state.effective_reverse else card.rank_value),
    )[: pending.count]
    _apply_pending_cards(state, cards)


def _finalize_post_play(state: GameState) -> None:
    context = state.pending_post_play
    if context is None:
        return
    player = context.player_index

    if context.forbidden_finish:
        if player not in state.penalty_players:
            # 後から禁止上がりした人ほど、先に順位へ入る（最初の違反者が最下位）。
            state.penalty_players.insert(0, player)
        context.messages.append("禁止上がり：最下位側へ降格")
        _complete_ranking_if_needed(state)
    else:
        context.messages.extend(_register_finish_and_capital_fall(state, player))

    if context.clear_effect is not None:
        state.pending_display = PendingDisplay(context.clear_effect, player)
        if context.clear_effect == "eight_cut":
            context.messages.append("8切り")
        else:
            context.messages.append("スペード3返し")
        state.message = "／".join(context.messages)
        state.pending_post_play = None
        return

    state.pending_post_play = None
    if state.game_over:
        state.current_player = -1
        state.message = "／".join(context.messages + ["ゲーム終了"])
        return

    next_turn = next_player(
        state,
        player,
        steps=1 + context.skip_count,
    )
    if next_turn is None:
        # パス済みの人しか残っていない場合は場を流す。
        leader = state.last_played_player
        clear_table(state)
        if leader is not None and state.hands[leader]:
            next_turn = leader
        else:
            next_turn = next_player(state, player, ignore_passed=True)
    if next_turn is None:
        _complete_ranking_if_needed(state)
        return

    state.current_player = next_turn
    state.turn_started_at = 0
    state.message = "／".join(context.messages)


def resolve_pending_display(state: GameState) -> None:
    pending = state.pending_display
    if pending is None:
        return
    player = pending.player_index
    effect_name = "8切り" if pending.effect == "eight_cut" else "スペード3返し"
    clear_table(state)
    state.pending_display = None

    if state.game_over:
        state.current_player = -1
        state.message = f"{effect_name}！ゲーム終了"
        return

    if state.hands[player] and player not in state.penalty_players:
        state.current_player = player
    else:
        candidate = next_player(state, player, ignore_passed=True)
        if candidate is None:
            _complete_ranking_if_needed(state)
            return
        state.current_player = candidate
    state.message = f"{effect_name}！場が流れ、{PLAYER_NAMES[state.current_player]}から再開"
    state.turn_started_at = 0


# ---------------------------------------------------------------------------
# カードを出す・パス
# ---------------------------------------------------------------------------


def play_cards(state: GameState, player_index: int, cards: list[Card]) -> tuple[bool, str]:
    valid, error, pattern = validate_play(state, player_index, cards)
    if not valid or pattern is None:
        return False, error

    previous_table = state.table_pattern
    spade_return = is_spade_three_return(pattern, previous_table, state.rules)
    forbidden_finish = is_forbidden_finish(
        state,
        pattern,
        len(state.hands[player_index]) - len(cards),
    )

    for card in cards:
        state.hands[player_index].remove(card)
    state.hands[player_index].sort(key=card_sort_key)

    state.table_cards = list(pattern.cards)
    state.table_pattern = pattern
    state.last_played_player = player_index
    state.passed_players.discard(player_index)
    state.first_turn = False
    state.selected_indices.clear()

    messages = [f"{PLAYER_NAMES[player_index]}：{_format_cards(pattern.cards)}"]

    lock_message = _update_suit_lock(state, pattern)
    if lock_message:
        messages.append(lock_message)

    if state.rules.revolution and _revolution_trigger(pattern):
        state.revolution = not state.revolution
        messages.append("革命" if state.revolution else "革命返し")

    if state.rules.eleven_back and pattern.represents_rank("J"):
        state.eleven_back = True
        messages.append("11バック")

    seven_count = pattern.effect_count("7") if state.rules.seven_pass else 0
    ten_count = pattern.effect_count("10") if state.rules.ten_discard else 0
    skip_count = pattern.effect_count("5") if state.rules.five_skip else 0
    if skip_count:
        messages.append(f"5飛び×{skip_count}")

    clear_effect: str | None = None
    if spade_return:
        clear_effect = "spade_three"
    elif state.rules.eight_cut and pattern.represents_rank("8"):
        clear_effect = "eight_cut"

    context = PostPlayContext(
        player_index=player_index,
        pattern=pattern,
        skip_count=skip_count,
        seven_count=seven_count,
        ten_count=ten_count,
        clear_effect=clear_effect,
        forbidden_finish=forbidden_finish,
        messages=messages,
    )
    state.pending_post_play = context
    _start_next_pending_effect(state)
    return True, ""


def pass_turn(state: GameState, player_index: int) -> tuple[bool, str]:
    if player_index != state.current_player:
        return False, "現在の手番ではありません"
    if state.table_pattern is None:
        return False, "場が空のときはパスできません"
    if state.pending_selection or state.pending_display:
        return False, "効果の処理中です"

    state.passed_players.add(player_index)
    state.selected_indices.clear()

    leader = state.last_played_player
    challengers = [
        player
        for player in active_players(state)
        if player != leader and player not in state.rankings
    ]
    all_passed = leader is not None and all(
        player in state.passed_players for player in challengers
    )

    if all_passed:
        old_leader = leader
        clear_table(state)
        if old_leader is not None and state.hands[old_leader]:
            state.current_player = old_leader
        else:
            candidate = next_player(state, player_index, ignore_passed=True)
            if candidate is None:
                _complete_ranking_if_needed(state)
                return True, "場が流れました"
            state.current_player = candidate
        state.message = f"場が流れ、{PLAYER_NAMES[state.current_player]}から再開"
        return True, ""

    candidate = next_player(state, player_index)
    if candidate is None:
        return False, "次のプレイヤーを決められませんでした"
    state.current_player = candidate
    state.message = f"{PLAYER_NAMES[player_index]}はパス"
    return True, ""


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------


def _generate_group_candidates(hand: list[Card], rules: RuleSettings) -> list[list[Card]]:
    joker = next((card for card in hand if card.is_joker), None)
    groups: dict[str, list[Card]] = {}
    for card in hand:
        if not card.is_joker:
            groups.setdefault(card.rank, []).append(card)

    candidates: list[list[Card]] = [[card] for card in hand]
    for cards in groups.values():
        for count in range(2, min(4, len(cards)) + 1):
            candidates.append(cards[:count])
        if rules.joker and joker is not None:
            for normal_count in range(1, min(3, len(cards)) + 1):
                candidates.append(cards[:normal_count] + [joker])
    return candidates


def _generate_straight_candidates(hand: list[Card], rules: RuleSettings) -> list[list[Card]]:
    if not rules.staircase:
        return []
    candidates: list[list[Card]] = []
    max_value = RANKS.index("A")
    by_suit: dict[str, dict[int, Card]] = {suit: {} for suit in SUITS}
    for card in hand:
        if not card.is_joker and card.rank_value <= max_value:
            by_suit[card.suit][card.rank_value] = card

    for suit_map in by_suit.values():
        for start in range(max_value + 1):
            sequence: list[Card] = []
            for value in range(start, max_value + 1):
                card = suit_map.get(value)
                if card is None:
                    break
                sequence.append(card)
                if len(sequence) >= 3:
                    candidates.append(sequence.copy())
    return candidates


def generate_cpu_candidates(state: GameState, player_index: int) -> list[list[Card]]:
    hand = state.hands[player_index]
    candidates = _generate_group_candidates(hand, state.rules)
    candidates.extend(_generate_straight_candidates(hand, state.rules))

    unique: dict[tuple[Card, ...], list[Card]] = {}
    for cards in candidates:
        key = tuple(sorted(cards, key=card_sort_key))
        unique[key] = cards
    return list(unique.values())


def choose_cpu_play(state: GameState, player_index: int) -> list[Card]:
    legal: list[tuple[list[Card], PlayPattern]] = []
    for cards in generate_cpu_candidates(state, player_index):
        valid, _, pattern = validate_play(state, player_index, cards)
        if valid and pattern is not None:
            legal.append((cards, pattern))
    if not legal:
        return []

    def score(item: tuple[list[Card], PlayPattern]) -> tuple[int, int, int, int]:
        cards, pattern = item
        joker_penalty = 1 if pattern.is_single_joker else 0
        special_bonus = 0
        if state.table_pattern is None:
            if state.rules.revolution and _revolution_trigger(pattern):
                special_bonus -= 3
            if pattern.kind == "straight":
                special_bonus -= 1
        strength = -pattern.strength if state.effective_reverse else pattern.strength
        # 場が空なら枚数を多く、競り中は必要最小限の強さを優先。
        count_score = -pattern.count if state.table_pattern is None else pattern.count
        return joker_penalty, special_bonus, count_score, strength

    legal.sort(key=score)
    return legal[0][0]


def process_cpu_turn(state: GameState) -> None:
    if state.current_player == 0 or state.game_over:
        return
    cards = choose_cpu_play(state, state.current_player)
    if cards:
        success, message = play_cards(state, state.current_player, cards)
    else:
        success, message = pass_turn(state, state.current_player)
    if not success:
        state.message = message


# ---------------------------------------------------------------------------
# 表示用
# ---------------------------------------------------------------------------


def state_status_lines(state: GameState) -> list[str]:
    lines: list[str] = []
    lines.append("革命中" if state.revolution else "通常")
    if state.eleven_back:
        lines.append("11バック中")
    if state.locked_suits:
        lines.append("縛り：" + "・".join(state.locked_suits))
    return lines


def table_description(state: GameState) -> str:
    pattern = state.table_pattern
    if pattern is None:
        return "場：なし"
    if pattern.kind == "straight":
        return f"場：{pattern.count}枚階段"
    if pattern.is_single_joker:
        return "場：JOKER"
    return f"場：{pattern.count}枚組・{pattern.primary_rank}"
