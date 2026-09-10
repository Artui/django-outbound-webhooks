"""Reading a status code as a verdict."""

from __future__ import annotations

import pytest

from django_outbound_webhooks.delivery.classify_response import classify_response
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict


@pytest.mark.parametrize("status", [200, 201, 202, 204, 299])
def test_2xx_succeeded(status: int) -> None:
    assert classify_response(status) is DeliveryVerdict.SUCCEEDED


@pytest.mark.parametrize("status", [500, 502, 503, 504, 599])
def test_5xx_is_worth_another_go(status: int) -> None:
    assert classify_response(status) is DeliveryVerdict.RETRY


@pytest.mark.parametrize("status", [408, 429])
def test_the_two_4xx_that_mean_later(status: int) -> None:
    # The endpoint asking for time, rather than refusing.
    assert classify_response(status) is DeliveryVerdict.RETRY


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 422, 451])
def test_every_other_4xx_is_permanent(status: int) -> None:
    # 410 Gone is the specification's retirement signal, and the rest are no
    # better: a malformed body or a refused credential is identical next time.
    assert classify_response(status) is DeliveryVerdict.PERMANENT


@pytest.mark.parametrize("status", [100, 101, 301, 302, 307, 308])
def test_1xx_and_3xx_are_permanent_rather_than_retried(status: int) -> None:
    # The client follows redirects itself, so a 3xx arriving here means the
    # budget ran out. Neither heals on a retry.
    assert classify_response(status) is DeliveryVerdict.PERMANENT


def test_the_boundaries_are_where_they_claim_to_be() -> None:
    # 199 and 300 are the two that a >= / > slip would move.
    assert classify_response(199) is DeliveryVerdict.PERMANENT
    assert classify_response(200) is DeliveryVerdict.SUCCEEDED
    assert classify_response(299) is DeliveryVerdict.SUCCEEDED
    assert classify_response(300) is DeliveryVerdict.PERMANENT
    assert classify_response(499) is DeliveryVerdict.PERMANENT
    assert classify_response(500) is DeliveryVerdict.RETRY
