"""End-to-end tests for both frontends, driven the way a user drives them."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from hanoi_crossing.cli import random_play, replay

BRIEF_EXAMPLE: dict[str, Any] = {
    "version": 1,
    "disks_per_player": 1,
    "turn_order": ["A", "B", "A"],
    "moves": [
        {"action": "lift", "pole": "1a"},
        {"action": "lift", "pole": "1b"},
        {"action": "place", "pole": "3a"},
    ],
}


def write(tmp_path: Path, document: dict[str, Any]) -> str:
    path = tmp_path / "game.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


# ------------------------------------------------------------------------ replay


def test_replay_runs_the_briefs_example_and_reports_a_win_for_a(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert replay.main([write(tmp_path, BRIEF_EXAMPLE)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["outcome"] == {"kind": "win", "players": ["A"]}
    assert output["turns_played"] == 3
    assert output["illegal_actions"] == 0
    assert output["final_state"]["poles"]["3a"] == [1]
    assert output["final_state"]["hands"] == {"A": None, "B": 2}


def test_replay_reads_stdin_when_given_a_dash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = json.dumps(BRIEF_EXAMPLE).encode()
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload)))

    assert replay.main(["-"]) == 0
    assert json.loads(capsys.readouterr().out)["outcome"]["kind"] == "win"


def test_replay_counts_illegal_moves_without_failing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = {
        "disks_per_player": 2,
        "turn_order": ["A", "A"],
        # 1b is B's pole; A cannot see it, so the turn is wasted.
        "moves": [{"action": "lift", "pole": "1b"}, {"action": "skip"}],
    }
    assert replay.main([write(tmp_path, document)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["illegal_actions"] == 1
    assert output["outcome"]["kind"] == "unfinished"


def test_replay_reports_a_bad_transcript_on_stderr_and_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert replay.main([write(tmp_path, {"disks_per_player": 1})]) == 2
    assert "missing required field" in capsys.readouterr().err


def test_replay_reports_a_missing_file_and_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert replay.main([str(tmp_path / "absent.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


# ------------------------------------------------------------------ random play


def test_random_play_reports_a_complete_result(capsys: pytest.CaptureFixture[str]) -> None:
    assert random_play.main(["--disks", "2", "--seed", "7", "--max-turns", "50"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["seed"] == 7
    assert output["games"] == 1
    assert set(output["outcomes"]) == {"win", "draw", "unfinished"}
    assert sum(output["outcomes"].values()) == 1


def test_the_same_seed_gives_the_same_game(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--disks", "3", "--seed", "1234", "--max-turns", "200"]
    random_play.main(args)
    first = capsys.readouterr().out
    random_play.main(args)
    assert capsys.readouterr().out == first


def test_different_seeds_diverge(capsys: pytest.CaptureFixture[str]) -> None:
    random_play.main(["--disks", "3", "--seed", "1", "--max-turns", "200"])
    first = capsys.readouterr().out
    random_play.main(["--disks", "3", "--seed", "2", "--max-turns", "200"])
    assert capsys.readouterr().out != first


def test_an_omitted_seed_is_generated_and_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An interesting unseeded run has to be reproducible afterwards."""
    assert random_play.main(["--disks", "1", "--max-turns", "10"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out)["seed"], int)


def test_many_games_are_summarised(capsys: pytest.CaptureFixture[str]) -> None:
    assert random_play.main(["--games", "25", "--seed", "3", "--max-turns", "60"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["games"] == 25
    assert sum(output["outcomes"].values()) == 25
    assert "result" not in output, "per-game detail is only useful for a single game"


def test_a_random_turn_order_is_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    assert random_play.main(["--turn-order", "random", "--seed", "5"]) == 0
    assert json.loads(capsys.readouterr().out)["turn_order"] == "random"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--disks", "0"], "--disks must be between"),
        (["--disks", "99"], "--disks must be between"),
        (["--max-turns", "-1"], "--max-turns cannot be negative"),
        (["--games", "0"], "--games must be at least 1"),
        (["--emit-transcript", "--games", "2"], "needs exactly one game"),
    ],
)
def test_bad_arguments_exit_two_with_a_message(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert random_play.main(argv) == 2
    assert message in capsys.readouterr().err


# ------------------------------------------------------------------ round trip


def test_a_generated_transcript_replays_to_the_same_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The strongest check that the two frontends agree: generate a game, then replay it."""
    seed = ["--disks", "2", "--seed", "99", "--max-turns", "120"]

    assert random_play.main([*seed, "--emit-transcript"]) == 0
    transcript = json.loads(capsys.readouterr().out)

    assert random_play.main(seed) == 0
    direct = json.loads(capsys.readouterr().out)["result"]

    assert replay.main([write(tmp_path, transcript)]) == 0
    replayed = json.loads(capsys.readouterr().out)

    assert replayed == direct


def test_an_emitted_transcript_records_only_the_turns_actually_played(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert random_play.main(["--disks", "1", "--seed", "4", "--max-turns", "500"]) == 0
    played = json.loads(capsys.readouterr().out)["result"]["turns_played"]

    assert (
        random_play.main(["--disks", "1", "--seed", "4", "--max-turns", "500", "--emit-transcript"])
        == 0
    )
    transcript = json.loads(capsys.readouterr().out)

    assert len(transcript["moves"]) == played
    assert len(transcript["turn_order"]) == played


def test_the_shipped_example_file_replays_to_the_briefs_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """examples/ ships with the repo, so an edit to it has to fail the suite."""
    example = Path(__file__).resolve().parent.parent / "examples" / "brief-example.json"

    assert replay.main([str(example)]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["outcome"] == {"kind": "win", "players": ["A"]}
    assert result["final_state"]["hands"] == {"A": None, "B": 2}
    assert result["final_state"]["poles"]["3a"] == [1]
