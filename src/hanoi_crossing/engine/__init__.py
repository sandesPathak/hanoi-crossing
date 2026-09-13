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
from hanoi_crossing.engine.rules import can_place_on, legal_actions, observe

__all__ = [
    "VISIBLE_POLES",
    "Action",
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
    "initial_state",
    "legal_actions",
    "observe",
]
