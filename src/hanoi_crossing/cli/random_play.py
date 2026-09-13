"""Random-play frontend: both players choose uniformly among their legal actions.

This doubles as the proof that the engine is agent-ready. The random player sees only an
Observation and calls `legal_actions` on it, exactly as an RL policy or a remote client
would -- it has no access to the board the replay frontend builds.
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from collections import Counter
from collections.abc import Sequence

from hanoi_crossing.engine import (
    Action,
    Observation,
    OutcomeKind,
    Player,
    Policy,
    initial_state,
    legal_actions,
    run_match,
)
from hanoi_crossing.transcript import (
    MAX_DISKS_PER_PLAYER,
    Transcript,
    render,
    render_transcript,
)

EXIT_OK = 0
EXIT_BAD_ARGS = 2

DEFAULT_DISKS = 3
DEFAULT_MAX_TURNS = 1_000
SEED_BITS = 32


def _turn_order(rng: random.Random, turns: int, *, shuffled: bool) -> list[Player]:
    """Turn order is the frontend's business; the engine assumes nothing about it."""
    if shuffled:
        return [rng.choice(list(Player)) for _ in range(turns)]
    return [Player.A if index % 2 == 0 else Player.B for index in range(turns)]


def _random_policy(rng: random.Random, log: list[tuple[Player, Action]] | None) -> Policy:
    def policy(observation: Observation) -> Action:
        # Uniform over legal actions, Skip included: it is a legal move, and leaving it
        # out would quietly make this a different agent from the one the rules describe.
        action = rng.choice(legal_actions(observation))
        if log is not None:
            log.append((observation.player, action))
        return action

    return policy


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hanoi-random",
        description="Play Hanoi Crossing with both players choosing random legal actions.",
    )
    parser.add_argument("--disks", type=int, default=DEFAULT_DISKS, help="disks per player")
    parser.add_argument("--seed", type=int, default=None, help="seed; random if omitted")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--games", type=int, default=1, help="how many games to simulate")
    parser.add_argument(
        "--turn-order",
        choices=["alternating", "random"],
        default="alternating",
    )
    parser.add_argument(
        "--emit-transcript",
        action="store_true",
        help="print a replayable transcript of the game instead of its result",
    )
    return parser


def _validate(args: argparse.Namespace) -> str | None:
    """Return an error message, or None if the arguments make sense together."""
    if not 1 <= args.disks <= MAX_DISKS_PER_PLAYER:
        return f"--disks must be between 1 and {MAX_DISKS_PER_PLAYER}"
    if args.max_turns < 0:
        return "--max-turns cannot be negative"
    if args.games < 1:
        return "--games must be at least 1"
    if args.emit_transcript and args.games != 1:
        return "--emit-transcript needs exactly one game"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if (problem := _validate(args)) is not None:
        print(f"error: {problem}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # A reported seed makes any interesting run reproducible, including an unseeded one.
    seed: int = args.seed if args.seed is not None else secrets.randbelow(2**SEED_BITS)
    rng = random.Random(seed)  # noqa: S311 - reproducible simulation, not security
    shuffled: bool = args.turn_order == "random"

    if args.emit_transcript:
        json.dump(_emit(args, rng, shuffled=shuffled), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return EXIT_OK

    json.dump(_simulate(args, rng, seed, shuffled=shuffled), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return EXIT_OK


def _emit(args: argparse.Namespace, rng: random.Random, *, shuffled: bool) -> dict[str, object]:
    log: list[tuple[Player, Action]] = []
    policy = _random_policy(rng, log)
    run_match(
        initial_state(args.disks),
        _turn_order(rng, args.max_turns, shuffled=shuffled),
        policy,
    )
    return render_transcript(
        Transcript(
            disks_per_player=args.disks,
            turn_order=tuple(player for player, _ in log),
            moves=tuple(action for _, action in log),
        )
    )


def _simulate(
    args: argparse.Namespace, rng: random.Random, seed: int, *, shuffled: bool
) -> dict[str, object]:
    games: int = args.games
    outcomes: Counter[str] = Counter()
    results = []

    for _ in range(games):
        result = run_match(
            initial_state(args.disks),
            _turn_order(rng, args.max_turns, shuffled=shuffled),
            _random_policy(rng, None),
        )
        outcomes[str(result.outcome.kind)] += 1
        if games == 1:
            results.append(render(result))

    summary: dict[str, object] = {
        "seed": seed,
        "disks_per_player": args.disks,
        "games": games,
        "turn_order": args.turn_order,
        "outcomes": {kind.value: outcomes[kind.value] for kind in OutcomeKind},
    }
    if results:
        summary["result"] = results[0]
    return summary


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
