"""Driver tests: turn order comes from outside, and a win stops the game at once."""

from __future__ import annotations

from collections.abc import Iterator

from hanoi_crossing.engine import (
    Action,
    GameState,
    Lift,
    Observation,
    Outcome,
    OutcomeKind,
    Place,
    Player,
    Pole,
    Policy,
    Skip,
    initial_state,
    run_match,
)


def scripted(moves: list[Action]) -> tuple[Policy, Iterator[Action]]:
    """A policy that plays a fixed list, so replay and random play share one driver."""
    remaining = iter(moves)

    def policy(_: Observation) -> Action:
        return next(remaining)

    return policy, remaining


def board(**poles: tuple[int, ...]) -> GameState:
    filled = {pole: poles.get(pole.name.lower(), ()) for pole in Pole}
    hands: dict[Player, int | None] = {Player.A: None, Player.B: None}
    return GameState(poles=filled, hands=hands, disks_per_player=1)


def test_the_briefs_example_runs_end_to_end_through_the_driver() -> None:
    policy, _ = scripted([Lift(Pole.A_HOME), Lift(Pole.B_HOME), Place(Pole.A_GOAL)])
    result = run_match(initial_state(1), [Player.A, Player.B, Player.A], policy)

    assert result.outcome == Outcome(kind=OutcomeKind.WIN, players=(Player.A,))
    assert result.turns_played == 3
    assert result.illegal_actions == 0


def test_a_win_stops_the_game_before_the_turn_order_is_exhausted() -> None:
    """Three more turns are offered after the winning move; none should be played."""
    policy, remaining = scripted([Lift(Pole.A_HOME), Place(Pole.A_GOAL), Skip(), Skip(), Skip()])
    order = [Player.A, Player.A, Player.B, Player.A, Player.B]
    result = run_match(initial_state(1), order, policy)

    assert result.outcome.kind is OutcomeKind.WIN
    assert result.turns_played == 2
    assert len(list(remaining)) == 3, "unplayed moves should be left untouched"


def test_illegal_actions_are_counted_and_still_consume_a_turn() -> None:
    policy, _ = scripted([Lift(Pole.B_HOME), Lift(Pole.SHARED), Skip()])
    result = run_match(initial_state(2), [Player.A, Player.A, Player.A], policy)

    assert result.turns_played == 3
    assert result.illegal_actions == 2


def test_an_empty_turn_order_plays_nothing() -> None:
    policy, _ = scripted([])
    result = run_match(initial_state(2), [], policy)

    assert result.turns_played == 0
    assert result.outcome.kind is OutcomeKind.UNFINISHED


def test_running_out_of_turns_is_unfinished_not_a_loss() -> None:
    policy, _ = scripted([Skip(), Skip()])
    result = run_match(initial_state(2), [Player.A, Player.B], policy)

    assert result.outcome == Outcome(kind=OutcomeKind.UNFINISHED, players=())


def test_two_players_finishing_together_is_a_draw() -> None:
    """Unreachable by playing -- see _outcome -- so it is set up directly.

    Both players need the shared pole clear, and the only way to clear it is to lift
    from it, which fills the lifter's hand and denies them the win. The engine still
    reports the case because run_match accepts any starting board.
    """
    both_won = board(a_goal=(1,), b_goal=(2,))
    policy, _ = scripted([])
    result = run_match(both_won, [Player.A, Player.B], policy)

    assert result.outcome.kind is OutcomeKind.DRAW
    assert result.outcome.players == (Player.A, Player.B)
    assert result.turns_played == 0


def test_a_board_that_is_already_won_plays_nothing() -> None:
    policy, remaining = scripted([Skip(), Skip()])
    result = run_match(board(a_goal=(1,)), [Player.B, Player.A], policy)

    assert result.turns_played == 0
    assert result.outcome.kind is OutcomeKind.WIN
    assert len(list(remaining)) == 2


def test_the_engine_assumes_no_turn_order_pattern() -> None:
    """A lopsided order must work exactly as an alternating one does."""
    policy, _ = scripted([Lift(Pole.A_HOME), Place(Pole.A_GOAL)])
    result = run_match(initial_state(1), [Player.A, Player.A], policy)

    assert result.outcome.kind is OutcomeKind.WIN
