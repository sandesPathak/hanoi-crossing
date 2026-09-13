"""Rules tests: the brief's worked example, every illegal branch, and the win predicate."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from hanoi_crossing.engine import (
    Action,
    GameFinishedError,
    GameState,
    Lift,
    Place,
    Player,
    Pole,
    Skip,
    can_place_on,
    has_won,
    initial_state,
    legal_actions,
    observe,
    step,
    winners,
)


def board(**poles: tuple[int, ...]) -> GameState:
    """Build a state from pole names, defaulting anything unnamed to empty."""
    filled = {pole: poles.get(pole.name.lower(), ()) for pole in Pole}
    hands: dict[Player, int | None] = {Player.A: None, Player.B: None}
    return GameState(poles=filled, hands=hands, disks_per_player=1)


def holding(state: GameState, player: Player, disk: int | None) -> GameState:
    hands = dict(state.hands)
    hands[player] = disk
    return GameState(poles=state.poles, hands=hands, disks_per_player=state.disks_per_player)


# --------------------------------------------------------------------------- setup


def test_initial_state_splits_disks_by_parity_largest_at_bottom() -> None:
    state = initial_state(3)
    assert state.poles[Pole.A_HOME] == (5, 3, 1)
    assert state.poles[Pole.B_HOME] == (6, 4, 2)
    assert state.poles[Pole.SHARED] == ()
    assert state.hands == {Player.A: None, Player.B: None}


@pytest.mark.parametrize("count", [0, -1])
def test_initial_state_rejects_a_non_positive_disk_count(count: int) -> None:
    with pytest.raises(ValueError, match="at least one disk"):
        initial_state(count)


def test_one_disk_each_is_the_smallest_legal_game() -> None:
    state = initial_state(1)
    assert state.poles[Pole.A_HOME] == (1,)
    assert state.poles[Pole.B_HOME] == (2,)


# --------------------------------------------------------------------- observation


def test_observation_hides_the_opponents_outer_poles() -> None:
    seen = observe(initial_state(2), Player.A)
    assert set(seen.poles) == {Pole.A_HOME, Pole.SHARED, Pole.A_GOAL}
    assert Pole.B_HOME not in seen.poles
    assert Pole.B_GOAL not in seen.poles


def test_observation_hides_the_opponents_hand() -> None:
    state = holding(initial_state(2), Player.B, 2)
    assert observe(state, Player.A).holding is None
    assert observe(state, Player.B).holding == 2


# ------------------------------------------------------------------- legal actions


def test_an_empty_handed_player_may_lift_from_any_non_empty_visible_pole() -> None:
    actions = legal_actions(observe(initial_state(2), Player.A))
    assert set(actions) == {Lift(Pole.A_HOME), Skip()}


def test_a_holding_player_may_only_place() -> None:
    state = step(initial_state(2), Player.A, Lift(Pole.A_HOME)).state
    actions = legal_actions(observe(state, Player.A))
    assert Lift(Pole.A_HOME) not in actions
    # Disk 1 in hand fits back on 3 at home, and on either empty pole.
    assert set(actions) == {Place(Pole.A_HOME), Place(Pole.SHARED), Place(Pole.A_GOAL), Skip()}


def test_placement_is_blocked_by_a_smaller_disk_underneath() -> None:
    state = holding(board(a_home=(3,), a_goal=(1,)), Player.A, 5)
    actions = legal_actions(observe(state, Player.A))
    # 5 fits on the empty shared pole only: 3 and 1 are both smaller.
    assert set(actions) == {Place(Pole.SHARED), Skip()}


def test_skip_is_always_available() -> None:
    empty = board()
    assert Skip() in legal_actions(observe(empty, Player.A))
    assert Skip() in legal_actions(observe(holding(empty, Player.A, 1), Player.A))


@pytest.mark.parametrize(
    ("stack", "disk", "allowed"),
    [((), 5, True), ((6,), 5, True), ((5,), 5, False), ((4,), 5, False)],
)
def test_placement_rule_needs_a_strictly_larger_disk(
    stack: tuple[int, ...], disk: int, allowed: bool
) -> None:
    assert can_place_on(stack, disk) is allowed


# -------------------------------------------------------------------- legal moves


def test_lift_takes_the_top_disk_into_the_hand() -> None:
    result = step(initial_state(2), Player.A, Lift(Pole.A_HOME))
    assert result.legal
    assert result.state.poles[Pole.A_HOME] == (3,)
    assert result.state.hands[Player.A] == 1


def test_place_puts_the_held_disk_on_top() -> None:
    state = holding(board(a_goal=(3,)), Player.A, 1)
    result = step(state, Player.A, Place(Pole.A_GOAL))
    assert result.legal
    assert result.state.poles[Pole.A_GOAL] == (3, 1)
    assert result.state.hands[Player.A] is None


def test_skip_is_legal_and_changes_nothing() -> None:
    state = initial_state(2)
    result = step(state, Player.A, Skip())
    assert result.legal
    assert result.state.poles == state.poles


def test_either_player_may_lift_from_the_shared_pole() -> None:
    state = board(shared=(4,))
    for player in (Player.A, Player.B):
        result = step(state, player, Lift(Pole.SHARED))
        assert result.legal
        assert result.state.hands[player] == 4


def test_a_player_may_carry_an_opponents_disk_to_their_own_goal() -> None:
    """Nothing in the rules ties a disk to its owner once it reaches the shared pole."""
    state = board(shared=(2,))
    lifted = step(state, Player.A, Lift(Pole.SHARED)).state
    placed = step(lifted, Player.A, Place(Pole.A_GOAL))
    assert placed.legal
    assert placed.state.poles[Pole.A_GOAL] == (2,)


# ------------------------------------------------------------------ illegal moves


@pytest.mark.parametrize(
    ("state_builder", "player", "action", "why"),
    [
        (lambda: initial_state(2), Player.A, Lift(Pole.B_HOME), "pole not visible"),
        (lambda: initial_state(2), Player.A, Lift(Pole.SHARED), "pole is empty"),
        (
            lambda: holding(initial_state(2), Player.A, 1),
            Player.A,
            Lift(Pole.A_HOME),
            "hand already full",
        ),
        (lambda: initial_state(2), Player.A, Place(Pole.A_GOAL), "holding nothing"),
        (
            lambda: holding(initial_state(2), Player.A, 1),
            Player.A,
            Place(Pole.B_GOAL),
            "pole not visible",
        ),
        (
            lambda: holding(board(a_goal=(1,)), Player.A, 3),
            Player.A,
            Place(Pole.A_GOAL),
            "disk underneath is smaller",
        ),
    ],
)
def test_an_illegal_action_wastes_the_turn_and_changes_nothing(
    state_builder: Callable[[], GameState], player: Player, action: Action, why: str
) -> None:
    state = state_builder()
    result = step(state, player, action)
    assert not result.legal, why
    assert result.state.poles == state.poles
    assert result.state.hands == state.hands


# ------------------------------------------------------------------ win condition


def test_a_player_wins_with_a_clear_home_a_clear_shared_pole_and_a_loaded_goal() -> None:
    assert has_won(board(a_goal=(3, 1)), Player.A)


def test_a_disk_left_on_the_shared_pole_blocks_the_win() -> None:
    assert not has_won(board(a_goal=(3, 1), shared=(2,)), Player.A)


def test_a_disk_left_at_home_blocks_the_win() -> None:
    assert not has_won(board(a_goal=(1,), a_home=(3,)), Player.A)


def test_an_empty_goal_is_not_a_win() -> None:
    """All poles clear is not victory -- the brief requires pole 3 to hold something."""
    assert not has_won(board(), Player.A)


def test_a_full_hand_blocks_the_win() -> None:
    assert not has_won(holding(board(a_goal=(1,)), Player.A, 3), Player.A)


def test_the_opponents_poles_do_not_affect_a_win() -> None:
    assert has_won(board(a_goal=(1,), b_home=(4, 2)), Player.A)


def test_the_briefs_worked_example_ends_with_a_win_for_a() -> None:
    """N=1, turn order [A, B, A]: A lifts, B lifts, A places on 3a and wins."""
    state = initial_state(1)

    first = step(state, Player.A, Lift(Pole.A_HOME))
    assert first.legal
    second = step(first.state, Player.B, Lift(Pole.B_HOME))
    assert second.legal
    third = step(second.state, Player.A, Place(Pole.A_GOAL))

    assert third.legal
    assert third.winners == frozenset({Player.A})
    assert third.state.poles[Pole.A_GOAL] == (1,)


def test_a_player_can_be_tipped_into_a_win_by_their_opponent() -> None:
    """A is one clear shared pole away from winning; B lifting from it does the work."""
    state = board(a_goal=(1,), shared=(2,), b_home=(4,))
    assert not winners(state)

    result = step(state, Player.B, Lift(Pole.SHARED))

    assert result.legal
    assert result.winners == frozenset({Player.A})


def test_two_simultaneous_winners_are_both_reported() -> None:
    state = board(a_goal=(1,), b_goal=(2,))
    assert winners(state) == frozenset({Player.A, Player.B})


def test_acting_on_a_finished_game_raises() -> None:
    won = board(a_goal=(1,))
    with pytest.raises(GameFinishedError):
        step(won, Player.B, Skip())
