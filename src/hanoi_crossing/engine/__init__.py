"""The Hanoi Crossing engine.

The public surface is deliberately small: build a state, observe it as one player,
enumerate that player's legal actions, apply one. Everything else is built on those.
"""

from hanoi_crossing.engine.model import (
    VISIBLE_POLES,
    Action,
    GameState,
    Lift,
    Observation,
    Place,
    Player,
    Pole,
    Skip,
    Stack,
    StepResult,
    initial_state,
)
from hanoi_crossing.engine.rules import (
    GameFinishedError,
    can_place_on,
    has_won,
    legal_actions,
    observe,
    step,
    winners,
)

__all__ = [
    "VISIBLE_POLES",
    "Action",
    "GameFinishedError",
    "GameState",
    "Lift",
    "Observation",
    "Place",
    "Player",
    "Pole",
    "Skip",
    "Stack",
    "StepResult",
    "can_place_on",
    "has_won",
    "initial_state",
    "legal_actions",
    "observe",
    "step",
    "winners",
]
