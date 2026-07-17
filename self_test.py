"""主要ルール・人数設定・CPU設定の簡易テスト。"""

from card import Card
from game_engine import (
    GameSession,
    analyze_play,
    choose_cpu_play,
    create_game,
    is_spade_three_return,
    rank_titles_for,
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


def test_player_counts() -> None:
    for player_count in (2, 3, 4):
        session = GameSession(
            RuleSettings.from_preset("standard"),
            player_count=player_count,
        )
        state = create_game(session)
        assert len(state.hands) == player_count
        assert sum(len(hand) for hand in state.hands) == 53
        assert len(rank_titles_for(player_count)) == player_count


def test_demo_mode() -> None:
    session = GameSession(
        RuleSettings.from_preset("party"),
        player_count=4,
        demo_mode=True,
    )
    state = create_game(session)
    assert state.current_player == 0
    assert any(card.suit == "♦" and card.rank == "3" for card in state.hands[0])
    assert any(card.suit == "♠" and card.rank == "3" for card in state.hands[0])
    assert sum(1 for card in state.hands[0] if card.rank == "9") == 4


def test_first_turn_validation() -> None:
    session = GameSession(RuleSettings.from_preset("simple"), player_count=3)
    state = create_game(session)
    player = state.current_player
    diamond_three = next(
        card
        for card in state.hands[player]
        if card.suit == "♦" and card.rank == "3"
    )
    ok, _, _ = validate_play(state, player, [diamond_three])
    assert ok


def test_cpu_difficulties() -> None:
    for difficulty in ("easy", "normal", "hard"):
        session = GameSession(
            RuleSettings.from_preset("standard"),
            player_count=2,
            cpu_difficulty=difficulty,
            demo_mode=True,
        )
        state = create_game(session)
        diamond_three = next(
            card
            for card in state.hands[0]
            if card.suit == "♦" and card.rank == "3"
        )
        ok, _, _ = validate_play(state, 0, [diamond_three])
        assert ok

        # CPU候補関数が難易度ごとに呼び出せることを確認する。
        state.current_player = 1
        state.first_turn = False
        state.table_cards.clear()
        state.table_pattern = None
        cards = choose_cpu_play(state, 1)
        assert cards


if __name__ == "__main__":
    test_patterns()
    test_spade_three_return()
    test_player_counts()
    test_demo_mode()
    test_first_turn_validation()
    test_cpu_difficulties()
    print("主要機能の簡易テストに成功しました。")
