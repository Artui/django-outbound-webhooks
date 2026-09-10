"""The policy object itself."""

from __future__ import annotations

import pytest
from tenacity import Retrying, stop_before_delay

from django_outbound_webhooks.delivery.retry_policy import retry_policy
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict


def test_it_stops_before_the_deadline_rather_than_after_it() -> None:
    # stop_after_delay notices a limit once it has been crossed; this one
    # refuses to start an attempt that would cross it, and the difference
    # between the two is a delivery that was sent and never recorded.
    policy = retry_policy(lease_seconds=30)
    assert isinstance(policy, Retrying)
    assert isinstance(policy.stop, stop_before_delay)
    assert policy.stop.max_delay == 18.0


def test_a_fresh_object_each_time() -> None:
    # Built per delivery rather than as a @retry decorator, because the timeout
    # and lease are per-endpoint values and a decorator fixes its policy at
    # import time.
    assert retry_policy(lease_seconds=30) is not retry_policy(lease_seconds=30)


def test_before_sleep_sees_every_attempt_but_the_last() -> None:
    """0.2.0's delivery log records inner attempts through this hook.

    Driven rather than inspected. Asserting the attribute was stored proves
    only that the constructor took the argument, and a bound method is a fresh
    object on every access, so identity does not even hold. Firing it is what
    shows the hook is wired to the loop.
    """
    seen: list[int] = []
    attempts = 0

    def one_attempt() -> DeliveryVerdict:
        nonlocal attempts
        attempts += 1
        return DeliveryVerdict.SUCCEEDED if attempts > 2 else DeliveryVerdict.RETRY

    policy = retry_policy(
        lease_seconds=30, before_sleep=lambda state: seen.append(state.attempt_number)
    )
    assert policy(one_attempt) is DeliveryVerdict.SUCCEEDED
    # Three attempts, two sleeps: the hook runs before a sleep, so the attempt
    # that finally succeeded is not followed by one.
    assert attempts == 3
    assert seen == [1, 2]


def test_a_lease_with_no_room_is_refused_when_the_policy_is_built() -> None:
    with pytest.raises(ValueError, match="no room to retry"):
        retry_policy(lease_seconds=5)
