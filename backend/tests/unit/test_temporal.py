"""Temporal validity parsing and comparison.

These exist because of a latent bug found by probing the Stage 4 conflict
spike: validity windows were compared as raw strings, so "2026-1-1" sorted
*after* "2026-01-01" and silently produced the wrong overlap verdict. Nothing
validated the format, so an unpadded date entered through the API would have
corrupted conflict findings with no error anywhere.
"""

import pytest
from pydantic import ValidationError

from kernote.domain.models import (
    ClaimKind,
    Memory,
    MemoryType,
    normalise_temporal,
    parse_temporal,
)
from kernote.maintain.conflicts import _windows_overlap


def _memory(**over) -> Memory:
    base = {
        "project_id": "p",
        "type": MemoryType.PROJECT_FACT,
        "title": "t",
        "content": "c",
        "claim_kind": ClaimKind.SOURCE_FACT,
        "importance": 0.5,
        "importance_reason": "r",
        "confidence": 0.5,
        "confidence_reason": "r",
        "extraction_method": "manual",
    }
    base.update(over)
    return Memory(**base)


# ------------------------------------------------------------------ parsing


@pytest.mark.parametrize(
    "value",
    [
        "2026-1-1",  # unpadded: the exact input that broke comparison
        "2026-1-31",
        "01/01/2026",  # not ISO at all
        "31/01/2026",
        "2026-13-01",  # impossible month
        "2026-02-30",  # impossible day
        "yesterday",
        "",
        "now",
    ],
)
def test_non_iso_values_are_rejected_at_the_boundary(value):
    with pytest.raises(ValidationError, match="ISO-8601"):
        _memory(valid_from=value)
    with pytest.raises(ValidationError, match="ISO-8601"):
        _memory(valid_until=value)


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("2026-03-11", "2026-03-11T00:00:00+00:00"),
        ("20260311", "2026-03-11T00:00:00+00:00"),
        ("2026-03-11T14:30:00Z", "2026-03-11T14:30:00+00:00"),
        ("2026-03-11 14:30:00", "2026-03-11T14:30:00+00:00"),
        ("2026-03-11T14:30:00+00:00", "2026-03-11T14:30:00+00:00"),
    ],
)
def test_accepted_forms_are_normalised_to_one_canonical_string(given, stored):
    """Four input spellings of the same instant must land on disk identically,
    so even a string comparison downstream cannot go wrong."""
    assert _memory(valid_from=given).valid_from == stored
    assert normalise_temporal(given) == stored


def test_naive_values_are_read_as_utc():
    assert parse_temporal("2026-03-11").tzinfo is not None
    assert parse_temporal("2026-03-11").utcoffset().total_seconds() == 0


def test_error_message_names_the_field_and_shows_an_example():
    with pytest.raises(ValidationError) as exc:
        _memory(valid_until="soon")
    msg = exc.value.errors()[0]["msg"]
    assert "valid_until" in msg
    assert "2026-03-11" in msg, "the message should show a valid example"
    assert "soon" in msg, "the message should quote what was given"


# ---------------------------------------------------------------- ordering


def test_backwards_window_is_rejected_across_mixed_valid_formats():
    """The ordering check must also compare as datetimes: a date-only value and
    a timestamp are both legal and must still order correctly."""
    with pytest.raises(ValidationError, match="precedes"):
        _memory(valid_from="2026-03-11T00:00:00Z", valid_until="2026-03-10")


def test_same_instant_in_two_spellings_is_a_valid_window():
    m = _memory(valid_from="2026-03-11", valid_until="2026-03-11T00:00:00+00:00")
    assert m.valid_from == m.valid_until


def test_correct_order_is_accepted():
    m = _memory(valid_from="2026-03-10", valid_until="2026-03-11T00:00:00Z")
    assert m.valid_from < m.valid_until  # safe now: both canonical


# ----------------------------------------------------------------- overlap


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (("2026-01-01", "2026-01-31"), ("2026-02-01", None), False),
        (("2026-01-01", "2026-02-15"), ("2026-02-01", None), True),
        (("2026-01-01", None), ("2026-02-01", None), True),
        ((None, None), (None, None), True),
        (("2026-01-01", "2026-01-31"), ("2026-01-31", None), True),  # touching
        (("2026-01-01", "2026-01-31"), ("2026-02-01T00:00:00Z", None), False),
    ],
)
def test_window_overlap(a, b, expected):
    assert _windows_overlap(a[0], a[1], b[0], b[1]) is expected


def test_unparseable_stored_bound_errs_towards_reporting(caplog):
    """A value hand-edited into the database must not silently hide a conflict.
    Treated as open-ended, and logged."""
    assert _windows_overlap("2026-1-1", None, "2026-02-01", None) is True


# ---------------------------------------------------------------- currency


def test_expired_window_is_not_current():
    assert not _memory(valid_from="2020-01-01", valid_until="2020-02-01").is_current


def test_open_ended_window_is_current():
    assert _memory(valid_from="2020-01-01").is_current


def test_future_window_end_is_current():
    assert _memory(valid_from="2026-01-01", valid_until="2099-01-01").is_current
