"""The rules themselves: what a player may see, what they may do, and who has won.

Every function here is pure. `step` takes a state and returns a new one, which is the
property that lets the same code back a replay CLI, an RL environment and a server
holding thousands of concurrent games without modification.
"""

from __future__ import annotations

from types import MappingProxyType

from hanoi_crossing.engine.model import (
    VISIBLE_POLES,
    GameState,
    Observation,
    Player,
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
