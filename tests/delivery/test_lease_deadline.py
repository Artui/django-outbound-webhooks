"""The arithmetic that keeps the inner retry inside the lease."""

from __future__ import annotations

import pytest

from django_outbound_webhooks.delivery.lease_deadline import lease_deadline


def test_it_subtracts_a_whole_timeout_and_the_margin() -> None:
    # A whole timeout, not a fraction of one. stop_before_delay keeps the next
    # sleep inside the limit and knows nothing about the attempt after it, so an
    # attempt may begin a hair under the deadline and run the full timeout past
    # it. Anything less than a whole timeout here reintroduces the overrun.
    assert lease_deadline(lease_seconds=30, timeout_seconds=10, margin_seconds=2) == 18


def test_the_worst_case_lands_inside_the_lease() -> None:
    # Stated as the property rather than the formula, so a change to the formula
    # has to keep the property.
    lease, timeout, margin = 30.0, 10.0, 2.0
    deadline = lease_deadline(lease_seconds=lease, timeout_seconds=timeout, margin_seconds=margin)
    worst_case = deadline + timeout
    assert worst_case <= lease - margin


@pytest.mark.parametrize(
    ("lease", "timeout", "margin"),
    [(10, 10, 2), (5, 10, 2), (12, 10, 2), (10, 8, 2)],
)
def test_no_room_is_refused_rather_than_clamped(
    lease: float, timeout: float, margin: float
) -> None:
    # Clamping to zero would turn "retry once or twice" into "never retry" with
    # nothing said, which is the quiet version of the bug this file exists for.
    with pytest.raises(ValueError, match="no room to retry"):
        lease_deadline(lease_seconds=lease, timeout_seconds=timeout, margin_seconds=margin)


def test_the_refusal_names_all_three_numbers() -> None:
    # An operator reading this has to know which of the three to change.
    with pytest.raises(ValueError) as raised:
        lease_deadline(lease_seconds=5, timeout_seconds=10, margin_seconds=2)
    message = str(raised.value)
    assert "5" in message and "10" in message and "2" in message
