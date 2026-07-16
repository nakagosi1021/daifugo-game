"""主要ルールの簡易テスト。`python self_test.py`で実行できます。"""

from card import Card
from game_engine import (
    GameSession,
    analyze_play,
    create_game,
    is_spade_three_return,
    validate_play,
)
from rules import RuleSettings


def test_patterns() -> None:
    rules = RuleSettings.from_preset("party")
    pair = analyze_play([Card("♠", "7"), Card("♥", "7")], rules)
    assert pair is not None and pair.kind == "group" and pair.count == 2

    straight = analyze_play(
        [Card("♠", "5"), Card("♠", "6"), Card("♠", "7")],
        rules,
    )
    assert straight is not None and straight.kind == "straight"


def test_spade_three_return() -> None:
    rules = RuleSettings.from_preset("party")
    joker = analyze_play([Card("JOKER", "JOKER")], rules)
    spade_three = analyze_play([Card("♠", "3")], rules)
    assert joker is not None and spade_three is not None
    assert is_spade_three_return(spade_three, joker, rules)


def test_new_game() -> None:
    session = GameSession(RuleSettings.from_preset("standard"))
    state = create_game(session)
    assert sum(len(hand) for hand in state.hands) == 53
    assert any(
        card.suit == "♦" and card.rank == "3"
        for card in state.hands[state.current_player]
    )


def test_first_turn_validation() -> None:
    session = GameSession(RuleSettings.from_preset("simple"))
    state = create_game(session)
    player = state.current_player
    diamond_three = next(
        card
        for card in state.hands[player]
        if card.suit == "♦" and card.rank == "3"
    )
    ok, _, _ = validate_play(state, player, [diamond_three])
    assert ok


if __name__ == "__main__":
    test_patterns()
    test_spade_three_return()
    test_new_game()
    test_first_turn_validation()
    print("主要ルールの簡易テストに成功しました。")
