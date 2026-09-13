"""Value types for a game of Hanoi Crossing: the board, the actions, and what a player sees.

Everything here is frozen. The engine never mutates a state in place, which is what
lets one process hold many independent games without them interfering.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

# Bottom-most disk first, so the top of the pole -- the only disk you can lift -- is [-1].
Stack = tuple[int, ...]


class Player(StrEnum):
    A = "A"
    B = "B"


class Pole(StrEnum):
    """The five poles, named as the brief's board names them: 1a - 2 - 3a, 1b - 2 - 3b."""

    A_HOME = "1a"
    A_GOAL = "3a"
    B_HOME = "1b"
    B_GOAL = "3b"
    SHARED = "2"


# Each player sees their own two poles plus the shared middle one, in board order.
# This mapping is the whole of the game's hidden information rule.
VISIBLE_POLES: Mapping[Player, tuple[Pole, Pole, Pole]] = MappingProxyType(
    {
        Player.A: (Pole.A_HOME, Pole.SHARED, Pole.A_GOAL),
        Player.B: (Pole.B_HOME, Pole.SHARED, Pole.B_GOAL),
    }
)


@dataclass(frozen=True, slots=True)
class Lift:
    """Take the top disk off a visible pole into the player's hand."""

    pole: Pole


@dataclass(frozen=True, slots=True)
class Place:
    """Put the held disk onto a visible pole."""

    pole: Pole


@dataclass(frozen=True, slots=True)
class Skip:
    """Do nothing. Always legal, so a player is never stuck without a move."""


Action = Lift | Place | Skip


@dataclass(frozen=True, slots=True)
class GameState:
    """The complete board. No player is ever handed one of these -- see Observation."""

    poles: Mapping[Pole, Stack]
    hands: Mapping[Player, int | None]
    disks_per_player: int


@dataclass(frozen=True, slots=True)
class Observation:
    """Everything one player is allowed to know, and nothing else.

    This is the entire agent-facing surface. An RL policy or a remote client receives
    an Observation and can enumerate its own legal moves from it, so the opponent's
    outer poles and hand are genuinely absent rather than merely left unread.
    """

    player: Player
    poles: Mapping[Pole, Stack]
    holding: int | None
    disks_per_player: int


@dataclass(frozen=True, slots=True)
class StepResult:
    """Outcome of one action: the resulting board, whether the rules accepted it, and
    who -- if anyone -- has now won."""

    state: GameState
    legal: bool
    winners: frozenset[Player]


def initial_state(disks_per_player: int) -> GameState:
    """Both players start with a full stack on their home pole, largest disk at the bottom.

    Player A owns the odd sizes and player B the even ones, so every disk in the game has
    a distinct size and the placement rule stays total across the shared pole.
    """
    if disks_per_player < 1:
        raise ValueError(f"need at least one disk per player, got {disks_per_player}")

    descending = range(disks_per_player - 1, -1, -1)
    poles: dict[Pole, Stack] = {
        Pole.A_HOME: tuple(2 * i + 1 for i in descending),
        Pole.B_HOME: tuple(2 * i + 2 for i in descending),
        Pole.SHARED: (),
        Pole.A_GOAL: (),
        Pole.B_GOAL: (),
    }
    hands: dict[Player, int | None] = {Player.A: None, Player.B: None}
    return GameState(
        poles=MappingProxyType(poles),
        hands=MappingProxyType(hands),
        disks_per_player=disks_per_player,
    )
