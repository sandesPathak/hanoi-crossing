"""End-to-end tests for both frontends, driven the way a user drives them."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from hanoi_crossing.cli import replay

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
