"""Parser tests. This is the untrusted boundary, so every rejection path is exercised."""

from __future__ import annotations

import json
from typing import Any

import pytest

from hanoi_crossing.engine import Lift, Place, Player, Pole, Skip
from hanoi_crossing.transcript import (
    MAX_DISKS_PER_PLAYER,
    MAX_INPUT_BYTES,
    MAX_MOVES,
    Transcript,
    TranscriptError,
    parse,
)


def document(**overrides: Any) -> str:
    base: dict[str, Any] = {
        "version": 1,
        "disks_per_player": 1,
        "turn_order": ["A", "B", "A"],
        "moves": [
            {"action": "lift", "pole": "1a"},
            {"action": "lift", "pole": "1b"},
            {"action": "place", "pole": "3a"},
        ],
    }
    base.update(overrides)
    return json.dumps(base)


# ------------------------------------------------------------------- happy path


def test_a_valid_transcript_parses_into_engine_types() -> None:
    parsed = parse(document())
    assert parsed.disks_per_player == 1
    assert parsed.turn_order == (Player.A, Player.B, Player.A)
    assert parsed.moves == (Lift(Pole.A_HOME), Lift(Pole.B_HOME), Place(Pole.A_GOAL))


def test_version_may_be_omitted() -> None:
    raw = json.loads(document())
    del raw["version"]
    assert parse(json.dumps(raw)).disks_per_player == 1


def test_bytes_are_accepted_as_well_as_text() -> None:
    assert parse(document().encode()).turn_order == (Player.A, Player.B, Player.A)


def test_a_skip_needs_no_pole() -> None:
    parsed = parse(document(turn_order=["A"], moves=[{"action": "skip"}]))
    assert parsed.moves == (Skip(),)


# -------------------------------------------------------------- malformed input


def test_input_over_the_size_cap_is_refused_before_parsing() -> None:
    with pytest.raises(TranscriptError, match="exceeds"):
        parse("x" * (MAX_INPUT_BYTES + 1))


def test_invalid_json_is_reported_as_such() -> None:
    with pytest.raises(TranscriptError, match="not valid JSON"):
        parse("{not json")


@pytest.mark.parametrize("payload", ["[]", '"a string"', "42", "null"])
def test_a_non_object_document_is_refused(payload: str) -> None:
    with pytest.raises(TranscriptError, match="expected a JSON object"):
        parse(payload)


def test_unknown_top_level_fields_are_refused_rather_than_ignored() -> None:
    with pytest.raises(TranscriptError, match="unknown transcript field"):
        parse(document(seed=7))


def test_an_unsupported_version_is_refused() -> None:
    with pytest.raises(TranscriptError, match="unsupported version"):
        parse(document(version=99))


# ------------------------------------------------------------------- field rules


@pytest.mark.parametrize("field", ["disks_per_player", "turn_order", "moves"])
def test_a_missing_required_field_is_refused(field: str) -> None:
    raw = json.loads(document())
    del raw[field]
    with pytest.raises(TranscriptError, match="missing required field"):
        parse(json.dumps(raw))


@pytest.mark.parametrize("value", ["3", 1.5, None, [], {}])
def test_a_non_integer_disk_count_is_refused(value: Any) -> None:
    with pytest.raises(TranscriptError, match="must be an integer"):
        parse(document(disks_per_player=value))


def test_a_boolean_disk_count_is_refused() -> None:
    """bool subclasses int, so this needs its own guard rather than an isinstance check."""
    with pytest.raises(TranscriptError, match="must be an integer"):
        parse(document(disks_per_player=True))


@pytest.mark.parametrize("value", [0, -1, MAX_DISKS_PER_PLAYER + 1])
def test_an_out_of_range_disk_count_is_refused(value: int) -> None:
    with pytest.raises(TranscriptError, match="must be between"):
        parse(document(disks_per_player=value))


@pytest.mark.parametrize("field", ["turn_order", "moves"])
def test_a_non_list_sequence_field_is_refused(field: str) -> None:
    with pytest.raises(TranscriptError, match="must be a list"):
        parse(document(**{field: "AAB"}))


def test_a_sequence_over_the_move_cap_is_refused() -> None:
    with pytest.raises(TranscriptError, match=f"exceeds {MAX_MOVES}"):
        parse(document(turn_order=["A"] * (MAX_MOVES + 1)))


def test_turn_order_and_moves_must_be_the_same_length() -> None:
    with pytest.raises(TranscriptError, match="each turn needs exactly one move"):
        parse(document(turn_order=["A"]))


@pytest.mark.parametrize("entry", ["C", "a", 1, None])
def test_an_unknown_player_in_the_turn_order_is_refused(entry: Any) -> None:
    with pytest.raises(TranscriptError, match="turn_order\\[0\\]"):
        parse(document(turn_order=[entry], moves=[{"action": "skip"}]))


# -------------------------------------------------------------------- move rules


@pytest.mark.parametrize("entry", ["lift", 3, None, []])
def test_a_non_object_move_is_refused(entry: Any) -> None:
    with pytest.raises(TranscriptError, match="must be an object"):
        parse(document(turn_order=["A"], moves=[entry]))


def test_unknown_move_fields_are_refused() -> None:
    with pytest.raises(TranscriptError, match=r"unknown moves\[0\] field"):
        parse(document(turn_order=["A"], moves=[{"action": "skip", "note": "hi"}]))


@pytest.mark.parametrize("kind", ["move", "", None, "LIFT"])
def test_an_unknown_action_is_refused(kind: Any) -> None:
    with pytest.raises(TranscriptError, match="action must be"):
        parse(document(turn_order=["A"], moves=[{"action": kind}]))


def test_a_skip_carrying_a_pole_is_refused() -> None:
    with pytest.raises(TranscriptError, match="skip takes no pole"):
        parse(document(turn_order=["A"], moves=[{"action": "skip", "pole": "2"}]))


@pytest.mark.parametrize("kind", ["lift", "place"])
def test_a_move_without_its_pole_is_refused(kind: str) -> None:
    with pytest.raises(TranscriptError, match="needs a pole"):
        parse(document(turn_order=["A"], moves=[{"action": kind}]))


@pytest.mark.parametrize("pole", ["1c", "4", "", None, 2])
def test_an_unknown_pole_is_refused(pole: Any) -> None:
    with pytest.raises(TranscriptError, match="pole must be one of"):
        parse(document(turn_order=["A"], moves=[{"action": "lift", "pole": pole}]))


def test_the_parser_accepts_every_pole_the_engine_defines() -> None:
    """Guards against the parser and the engine drifting apart on pole names."""
    for pole in Pole:
        parsed = parse(document(turn_order=["A"], moves=[{"action": "lift", "pole": str(pole)}]))
        assert parsed.moves == (Lift(pole),)


def test_an_empty_game_is_valid() -> None:
    assert parse(document(turn_order=[], moves=[])) == Transcript(1, (), ())


# ------------------------------------------------------- untrusted text in errors


@pytest.mark.parametrize(
    "hostile",
    ["\x1b[31mred\x1b[0m", "line\nbreak", "carriage\rreturn", "\x07bell"],
)
def test_control_characters_in_a_field_name_never_reach_the_terminal_raw(
    hostile: str,
) -> None:
    """Field names come from the document, so they are quoted before being reported."""
    with pytest.raises(TranscriptError) as caught:
        parse(document(**{hostile: 1}))

    message = str(caught.value)
    assert not any(char in message for char in "\x1b\n\r\x07")


def test_control_characters_in_a_pole_name_never_reach_the_terminal_raw() -> None:
    with pytest.raises(TranscriptError) as caught:
        parse(
            document(
                turn_order=["A"],
                moves=[{"action": "lift", "pole": "\x1b[31m1a\x1b[0m"}],
            )
        )
    assert "\x1b" not in str(caught.value)
