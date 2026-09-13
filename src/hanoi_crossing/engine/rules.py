"""The rules themselves: what a player may see, what they may do, and who has won.

Every function here is pure. `step` takes a state and returns a new one, which is the
property that lets the same code back a replay CLI, an RL environment and a server
holding thousands of concurrent games without modification.
"""

from __future__ import annotations

from types import MappingProxyType

from hanoi_crossing.engine.model import (
    VISIBLE_POLES,
    Action,
    GameState,
    Lift,
    Observation,
    Place,
    Player,
    Skip,
    Stack,
)


def observe(state: GameState, player: Player) -> Observation:
    """Project the board down to what `player` is entitled to see."""
    visible = {pole: state.poles[pole] for pole in VISIBLE_POLES[player]}
    return Observation(
        player=player,
        poles=MappingProxyType(visible),
        holding=state.hands[player],
        disks_per_player=state.disks_per_player,
    )


def can_place_on(stack: Stack, disk: int) -> bool:
    """Tower of Hanoi placement: an empty pole, or a strictly larger disk underneath.

    Size alone decides this. A disk's owner is irrelevant, so on the shared pole one
    player's disk may legally rest on the other's.
    """
    return not stack or stack[-1] > disk


def legal_actions(observation: Observation) -> tuple[Action, ...]:
    """Every action the engine will accept, derived from the observation alone.

    Taking an Observation rather than a GameState is the point: an external agent can
    enumerate its own moves without ever being handed the opponent's half of the board.
    """
    held = observation.holding
    moves: list[Action] = []
    if held is None:
        moves.extend(Lift(pole) for pole, stack in observation.poles.items() if stack)
    else:
        moves.extend(
            Place(pole) for pole, stack in observation.poles.items() if can_place_on(stack, held)
        )
    # Skip is always available, and comes last so the interesting moves read first.
    moves.append(Skip())
    return tuple(moves)
