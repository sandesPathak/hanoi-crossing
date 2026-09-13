"""Replay frontend: run a recorded game and print the final state.

Reads a transcript from a file or stdin, plays it through the engine, and writes the
result as JSON. It makes no decisions of its own -- every action comes from the file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from hanoi_crossing.engine import Action, Observation, Policy, initial_state, run_match
from hanoi_crossing.transcript import MAX_INPUT_BYTES, TranscriptError, parse, render

EXIT_OK = 0
EXIT_BAD_INPUT = 2


def _scripted(moves: Sequence[Action]) -> Policy:
    """Turn a recorded move list into a policy, so replay uses the ordinary driver."""
    remaining: Iterator[Action] = iter(moves)

    def policy(_: Observation) -> Action:
        return next(remaining)

    return policy


def _read_source(source: str) -> bytes:
    """Read at most one byte past the cap, so an enormous file is never loaded."""
    if source == "-":
        return sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    with Path(source).open("rb") as handle:
        return handle.read(MAX_INPUT_BYTES + 1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hanoi-replay",
        description="Replay a recorded Hanoi Crossing game and print the final state.",
    )
    parser.add_argument(
        "transcript",
        help="path to a transcript JSON file, or '-' to read from stdin",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    source: str = args.transcript

    try:
        transcript = parse(_read_source(source))
    except TranscriptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except OSError as exc:
        print(f"error: cannot read {source}: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    result = run_match(
        initial_state(transcript.disks_per_player),
        transcript.turn_order,
        _scripted(transcript.moves),
    )
    json.dump(render(result), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
