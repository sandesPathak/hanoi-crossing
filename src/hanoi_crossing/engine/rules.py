"""The rules themselves: what a player may see, what they may do, and who has won.

Every function here is pure. `step` takes a state and returns a new one, which is the
property that lets the same code back a replay CLI, an RL environment and a server
holding thousands of concurrent games without modification.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import assert_never

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
)


class GameFinishedError(RuntimeError):
    """Raised when an action is applied to a state that has already been won.

    This is a caller bug rather than a rule violation, so it raises instead of
    coming back as an illegal action.
    """


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


def has_won(state: GameState, player: Player) -> bool:
    """The brief's condition: hand empty, and of this player's poles only pole 3 has disks.

    Note what this does *not* require: that the disks on pole 3 are the player's own, or
    that all N of them are there. Read literally, a player whose disks were carried off
    through the shared pole can still win with whatever remains. That reading is kept --
    see the design notes in the README.
    """
    if state.hands[player] is not None:
        return False
    home, shared, goal = VISIBLE_POLES[player]
    return not state.poles[home] and not state.poles[shared] and bool(state.poles[goal])


def winners(state: GameState) -> frozenset[Player]:
    """Every player satisfying the win condition in this state.

    Evaluated as a predicate over the board, not as a consequence of the acting player's
    move. Because the shared pole must be clear to win, one player can be tipped over the
    line by their opponent lifting the last disk off it -- so both players are checked
    after every action, and a state satisfying both is a draw.
    """
    return frozenset(player for player in Player if has_won(state, player))


def step(state: GameState, player: Player, action: Action) -> StepResult:
    """Apply one action on `player`'s turn.

    An illegal action is not an error. The rules say it wastes the turn, so the original
    state comes back with `legal=False` and the caller counts it.
    """
    if winners(state):
        raise GameFinishedError("the game is already won; no further actions apply")

    applied = _apply(state, player, action)
    resolved = state if applied is None else applied
    return StepResult(state=resolved, legal=applied is not None, winners=winners(resolved))


def _apply(state: GameState, player: Player, action: Action) -> GameState | None:
    """Return the state after `action`, or None if the rules reject it."""
    match action:
        case Skip():
            return state
        case Lift(pole=pole):
            return _lift(state, player, pole)
        case Place(pole=pole):
            return _place(state, player, pole)
        case _:  # pragma: no cover - exhaustive over Action; guards future variants
            assert_never(action)


def _lift(state: GameState, player: Player, pole: Pole) -> GameState | None:
    if pole not in VISIBLE_POLES[player]:
        return None
    if state.hands[player] is not None:
        return None
    stack = state.poles[pole]
    if not stack:
        return None
    return _with(state, pole, stack[:-1], player, stack[-1])


def _place(state: GameState, player: Player, pole: Pole) -> GameState | None:
    if pole not in VISIBLE_POLES[player]:
        return None
    held = state.hands[player]
    if held is None:
        return None
    stack = state.poles[pole]
    if not can_place_on(stack, held):
        return None
    return _with(state, pole, (*stack, held), player, None)


def _with(
    state: GameState,
    pole: Pole,
    stack: Stack,
    player: Player,
    holding: int | None,
) -> GameState:
    """Copy the state with one pole and one hand replaced."""
    poles = dict(state.poles)
    poles[pole] = stack
    hands = dict(state.hands)
    hands[player] = holding
    return GameState(
        poles=MappingProxyType(poles),
        hands=MappingProxyType(hands),
        disks_per_player=state.disks_per_player,
    )
