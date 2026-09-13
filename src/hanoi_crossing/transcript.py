"""The on-disk game format: parsing recorded games in, rendering results out.

This module owns the only trust boundary in the program. Everything arriving here is
untrusted, so it is validated field by field, bounded, and converted into engine types
before any of it reaches the engine. See SECURITY.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from hanoi_crossing.engine import (
    Action,
    Lift,
    Place,
    Player,
    Pole,
    Skip,
)

# Bounds, chosen so a hostile file cannot exhaust memory or wedge the process. Hanoi needs
# 2^n - 1 moves for n disks, so 32 disks is already far past anything a person would replay.
MAX_INPUT_BYTES: Final = 1 << 20
MAX_DISKS_PER_PLAYER: Final = 32
MAX_MOVES: Final = 100_000

SUPPORTED_VERSION: Final = 1
_TOP_LEVEL_KEYS: Final = frozenset({"version", "disks_per_player", "turn_order", "moves"})
_MOVE_KEYS: Final = frozenset({"action", "pole"})


class TranscriptError(ValueError):
    """The input is not a transcript this program will run."""


@dataclass(frozen=True, slots=True)
class Transcript:
    disks_per_player: int
    turn_order: tuple[Player, ...]
    moves: tuple[Action, ...]


def parse(raw: str | bytes) -> Transcript:
    """Validate untrusted bytes into a Transcript, or raise TranscriptError."""
    if len(raw) > MAX_INPUT_BYTES:
        raise TranscriptError(f"input exceeds {MAX_INPUT_BYTES} bytes")

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranscriptError(f"input is not valid JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise TranscriptError(f"expected a JSON object, got {type(document).__name__}")

    _reject_unknown_keys(document, _TOP_LEVEL_KEYS, "transcript")
    _check_version(document.get("version", SUPPORTED_VERSION))

    disks = _require_int(document, "disks_per_player", low=1, high=MAX_DISKS_PER_PLAYER)
    turn_order = _parse_turn_order(_require_list(document, "turn_order"))
    moves = _parse_moves(_require_list(document, "moves"))

    if len(moves) != len(turn_order):
        raise TranscriptError(
            f"turn_order has {len(turn_order)} entries but moves has {len(moves)}; "
            "each turn needs exactly one move"
        )

    return Transcript(disks_per_player=disks, turn_order=turn_order, moves=moves)


def _reject_unknown_keys(value: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    """Unknown keys are refused rather than ignored, so a typo fails loudly.

    Names are quoted with !r before going into the message. They come from the untrusted
    document, and an unquoted one carrying terminal escapes would reach the operator's
    stderr intact.
    """
    unknown = sorted(set(value) - allowed)
    if unknown:
        listed = ", ".join(repr(name) for name in unknown)
        raise TranscriptError(f"unknown {where} field(s): {listed}")


def _check_version(version: object) -> None:
    if version != SUPPORTED_VERSION:
        raise TranscriptError(f"unsupported version {version!r}, expected {SUPPORTED_VERSION}")


def _require_int(document: dict[str, Any], key: str, *, low: int, high: int) -> int:
    if key not in document:
        raise TranscriptError(f"missing required field {key!r}")
    value = document[key]
    # bool is a subclass of int, and `True` is not a disk count.
    if not isinstance(value, int) or isinstance(value, bool):
        raise TranscriptError(f"{key} must be an integer, got {type(value).__name__}")
    if not low <= value <= high:
        raise TranscriptError(f"{key} must be between {low} and {high}, got {value}")
    return value


def _require_list(document: dict[str, Any], key: str) -> list[Any]:
    if key not in document:
        raise TranscriptError(f"missing required field {key!r}")
    value = document[key]
    if not isinstance(value, list):
        raise TranscriptError(f"{key} must be a list, got {type(value).__name__}")
    if len(value) > MAX_MOVES:
        raise TranscriptError(f"{key} exceeds {MAX_MOVES} entries")
    return value


def _parse_turn_order(entries: list[Any]) -> tuple[Player, ...]:
    players = {str(player) for player in Player}
    order: list[Player] = []
    for index, entry in enumerate(entries):
        if entry not in players:
            raise TranscriptError(
                f"turn_order[{index}]: expected one of {sorted(players)}, got {entry!r}"
            )
        order.append(Player(entry))
    return tuple(order)


def _parse_moves(entries: list[Any]) -> tuple[Action, ...]:
    return tuple(_parse_move(entry, index) for index, entry in enumerate(entries))


def _parse_move(entry: object, index: int) -> Action:
    if not isinstance(entry, dict):
        raise TranscriptError(f"moves[{index}] must be an object, got {type(entry).__name__}")
    _reject_unknown_keys(entry, _MOVE_KEYS, f"moves[{index}]")

    kind = entry.get("action")
    if kind == "skip":
        if "pole" in entry:
            raise TranscriptError(f"moves[{index}]: a skip takes no pole")
        return Skip()
    if kind in {"lift", "place"}:
        pole = _parse_pole(entry, index)
        return Lift(pole) if kind == "lift" else Place(pole)
    raise TranscriptError(f"moves[{index}]: action must be 'lift', 'place' or 'skip', got {kind!r}")


def _parse_pole(entry: dict[str, Any], index: int) -> Pole:
    if "pole" not in entry:
        raise TranscriptError(f"moves[{index}]: a {entry['action']!r} needs a pole")
    names = {str(pole) for pole in Pole}
    if entry["pole"] not in names:
        raise TranscriptError(
            f"moves[{index}]: pole must be one of {sorted(names)}, got {entry['pole']!r}"
        )
    return Pole(entry["pole"])
