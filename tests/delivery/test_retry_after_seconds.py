"""Reading an endpoint's Retry-After header."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from django_outbound_webhooks.delivery.retry_after_seconds import (
    HONOURED_STATUSES,
    retry_after_seconds,
)

NOW = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)


def test_a_number_of_seconds() -> None:
    assert retry_after_seconds("120", now=NOW) == 120.0


def test_surrounding_whitespace_is_ignored() -> None:
    assert retry_after_seconds("  120 ", now=NOW) == 120.0


def test_an_http_date_is_the_time_until_it() -> None:
    header = "Wed, 16 Sep 2026 12:02:00 GMT"
    assert retry_after_seconds(header, now=NOW) == 120.0


def test_a_date_in_the_obsolete_unknown_zone_is_read_as_utc() -> None:
    header = "Wed, 16 Sep 2026 12:02:00 -0000"
    assert retry_after_seconds(header, now=NOW) == 120.0


def test_a_date_already_past_means_now_rather_than_a_negative_delay() -> None:
    """The substrate refuses a negative delay, so this is the difference between
    retrying straight away and failing the delivery for a clock difference."""
    past = (NOW - timedelta(minutes=5)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert retry_after_seconds(past, now=NOW) == 0.0


def test_no_header_is_no_instruction() -> None:
    assert retry_after_seconds(None, now=NOW) is None


@pytest.mark.parametrize("header", ["soon", "-5", "1.5", "", "Wed, 99 Foo 2026"])
def test_a_header_that_cannot_be_read_is_no_instruction(header: str) -> None:
    assert retry_after_seconds(header, now=NOW) is None


def test_a_non_ascii_digit_is_not_a_number() -> None:
    """``str.isdigit`` says yes to a superscript two, and ``int`` then raises -
    inside a delivery, over a header."""
    assert "²".isdigit()
    assert retry_after_seconds("²", now=NOW) is None


def test_only_rate_limiting_and_unavailability_are_honoured() -> None:
    assert frozenset({429, 503}) == HONOURED_STATUSES
