import random

from game_engine import (
    GameSession,
    auto_resolve_pending_selection,
    choose_cpu_play,
    create_game,
    pass_turn,
    play_cards,
    resolve_pending_display,
)
from rules import RuleSettings


def play_one(player_count: int, difficulty: str, preset: str, demo: bool = False) -> None:
    session = GameSession(
        RuleSettings.from_preset(preset),
        player_count=player_count,
        cpu_difficulty=difficulty,
        demo_mode=demo,
    )
    state = create_game(session)
    for _ in range(5000):
        if state.pending_display is not None:
            resolve_pending_display(state)
            continue
        if state.pending_selection is not None:
            auto_resolve_pending_selection(state)
            continue
        if state.game_over:
            assert len(state.rankings) == player_count
            return
        player = state.current_player
        cards = choose_cpu_play(state, player)
        if cards:
            success, message = play_cards(state, player, cards)
        else:
            success, message = pass_turn(state, player)
        if not success:
            raise AssertionError((player_count, difficulty, preset, player, message))
    raise AssertionError(("not finished", player_count, difficulty, preset))


if __name__ == "__main__":
    random.seed(7)
    for player_count in (2, 3, 4):
        for difficulty in ("easy", "normal", "hard"):
            for preset in ("simple", "standard", "party"):
                for _ in range(3):
                    play_one(player_count, difficulty, preset)
            play_one(player_count, difficulty, "party", demo=True)
    print("automatic simulations passed")
