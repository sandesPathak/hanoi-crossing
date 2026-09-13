"""Property tests for the invariants the engine's correctness rests on.

These drive random legal play from a random state and assert the things that must never
stop being true, rather than checking one hand-picked sequence.
"""

from __future__ import annotations

import random
from itertools import pairwise

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hanoi_crossing.engine import (
    Action,
    GameState,
    Lift,
    Place,
    Player,
    Pole,
    Skip,
    initial_state,
    legal_actions,
    observe,
    step,
    winners,
)

MAX_DISKS = 4


def disks_in_play(state: GameState) -> list[int]:
    """Every disk on the board plus every disk in a hand."""
    held = [disk for disk in state.hands.values() if disk is not None]
    return sorted([disk for stack in state.poles.values() for disk in stack] + held)


def is_well_stacked(state: GameState) -> bool:
    """Bottom-to-top, every pole must be strictly decreasing."""
    return all(
        all(lower > upper for lower, upper in pairwise(stack)) for stack in state.poles.values()
    )


@st.composite
def reachable_state(draw: st.DrawFn) -> GameState:
    """A state reached by playing a random number of random *legal* actions."""
    disks = draw(st.integers(min_value=1, max_value=MAX_DISKS))
    turns = draw(st.integers(min_value=0, max_value=40))
    rng = random.Random(draw(st.integers(min_value=0, max_value=2**32 - 1)))

    state = initial_state(disks)
    for index in range(turns):
        if winners(state):
            break
        player = Player.A if index % 2 == 0 else Player.B
        action = rng.choice(legal_actions(observe(state, player)))
        state = step(state, player, action).state
    return state


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state())
def test_disks_are_never_created_or_destroyed(state: GameState) -> None:
    expected = sorted(range(1, 2 * state.disks_per_player + 1))
    assert disks_in_play(state) == expected


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state())
def test_no_disk_ever_rests_on_a_smaller_one(state: GameState) -> None:
    assert is_well_stacked(state)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state())
def test_a_player_never_holds_more_than_one_disk(state: GameState) -> None:
    for held in state.hands.values():
        assert held is None or isinstance(held, int)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state(), seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_every_enumerated_action_is_accepted_by_step(state: GameState, seed: int) -> None:
    """legal_actions must not offer anything step then rejects, or an agent cannot trust it."""
    if winners(state):
        return
    player = random.Random(seed).choice(list(Player))
    for action in legal_actions(observe(state, player)):
        assert step(state, player, action).legal, action


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state(), seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_step_never_mutates_the_state_it_was_given(state: GameState, seed: int) -> None:
    """The engine's reuse story depends on this: concurrent games must not alias."""
    if winners(state):
        return
    before_poles = dict(state.poles)
    before_hands = dict(state.hands)

    rng = random.Random(seed)
    player = rng.choice(list(Player))
    candidates: list[Action] = [
        Skip(),
        *[Lift(pole) for pole in Pole],
        *[Place(pole) for pole in Pole],
    ]
    step(state, player, rng.choice(candidates))

    assert state.poles == before_poles
    assert state.hands == before_hands


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(state=reachable_state(), seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_a_rejected_action_leaves_the_board_identical(state: GameState, seed: int) -> None:
    if winners(state):
        return
    rng = random.Random(seed)
    player = rng.choice(list(Player))
    candidates: list[Action] = [
        *[Lift(pole) for pole in Pole],
        *[Place(pole) for pole in Pole],
    ]

    for action in candidates:
        result = step(state, player, action)
        if not result.legal:
            assert result.state.poles == state.poles
            assert result.state.hands == state.hands
