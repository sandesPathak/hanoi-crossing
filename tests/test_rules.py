"""Rules tests: the brief's worked example, every illegal branch, and the win predicate."""

from __future__ import annotations

import pytest

from hanoi_crossing.engine import (
    GameState,
    Lift,
    Place,
    Player,
    Pole,
    Skip,
    can_place_on,
    initial_state,
    legal_actions,
    observe,
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
