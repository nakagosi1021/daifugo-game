from __future__ import annotations

from game_engine import GameSession, create_game, process_cpu_turn, rank_titles_for
from lan_common import legal_plays_for
from rules import RuleSettings


def main() -> None:
    for player_count in range(2, 7):
        session = GameSession(
            rules=RuleSettings.from_preset("standard"),
            player_count=player_count,
            human_players={0},
        )
        state = create_game(session)
        assert len(state.hands) == player_count
        assert len(rank_titles_for(player_count)) == player_count

    session = GameSession(
        rules=RuleSettings.from_preset("standard"),
        player_count=6,
        human_players=set(range(6)),
    )
    state = create_game(session)

    assert len(state.hands) == 6
    assert all(len(hand) == 8 for hand in state.hands)
    assert sum(len(hand) for hand in state.hands) == 48
    assert len(rank_titles_for(6)) == 6
    assert any(
        card.suit == "♦" and card.rank == "3"
        for hand in state.hands
        for card in hand
    )

    legal = legal_plays_for(state, state.current_player)
    assert legal, "開始プレイヤーに合法手がありません"

    cpu_session = GameSession(
        rules=RuleSettings.from_preset("standard"),
        player_count=6,
        human_players=set(),
    )
    cpu_state = create_game(cpu_session)
    before_counts = [len(hand) for hand in cpu_state.hands]
    process_cpu_turn(cpu_state)
    after_counts = [len(hand) for hand in cpu_state.hands]
    assert sum(after_counts) < sum(before_counts), "CPUの手番が進んでいません"

    print("6人LAN版の簡易テストに成功しました。")
    print("各プレイヤーの手札: 8枚")
    print(f"開始プレイヤー: 席{state.current_player + 1}")


if __name__ == "__main__":
    main()
