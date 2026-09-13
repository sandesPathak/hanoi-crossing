"""Driver that runs a game forward: a turn order, a policy, and a stopping rule.

The engine does not decide who moves next. Turn order arrives from outside as a plain
sequence, and every action comes from a policy, so a replay of recorded moves and a
random agent are the same code path with a different policy.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from hanoi_crossing.engine.model import Action, GameState, Observation, Player
from hanoi_crossing.engine.rules import observe, step, winners

# A policy is anything that turns what a player can see into what they do. This is the
# seam an RL agent, a scripted replay or a human client all plug into.
Policy = Callable[[Observation], Action]


class OutcomeKind(StrEnum):
    WIN = "win"
    DRAW = "draw"
    UNFINISHED = "unfinished"


@dataclass(frozen=True, slots=True)
class Outcome:
    kind: OutcomeKind
    players: tuple[Player, ...]


@dataclass(frozen=True, slots=True)
class MatchResult:
    final_state: GameState
    outcome: Outcome
    turns_played: int
    illegal_actions: int


def run_match(state: GameState, turn_order: Iterable[Player], policy: Policy) -> MatchResult:
    """Play until someone wins or the turn order runs out.

    A win ends the game immediately: any turns left in the sequence are not played. A
    state that is already won plays nothing, so callers may hand in an arbitrary board
    without checking it first.
    """
    turns_played = 0
    illegal_actions = 0
    current = state

    for player in turn_order:
        if winners(current):
            break
        result = step(current, player, policy(observe(current, player)))
        current = result.state
        turns_played += 1
        if not result.legal:
            illegal_actions += 1
        if result.winners:
            break

    return MatchResult(
        final_state=current,
        outcome=_outcome(current),
        turns_played=turns_played,
        illegal_actions=illegal_actions,
    )


def _outcome(state: GameState) -> Outcome:
    """Two simultaneous winners is a draw.

    Legal play cannot actually reach one. Both players need the shared pole empty, and
    the only way to empty it is to lift from it, which fills the lifter's hand and so
    denies them the win. The case is still handled because `run_match` accepts any
    starting board, including a constructed one.
    """
    won = tuple(sorted(winners(state)))
    if len(won) > 1:
        return Outcome(kind=OutcomeKind.DRAW, players=won)
    if won:
        return Outcome(kind=OutcomeKind.WIN, players=won)
    return Outcome(kind=OutcomeKind.UNFINISHED, players=())
