"""Sending a delivery, and the lease it must not outlive."""

from __future__ import annotations

import base64
import time

import httpx2
import pytest
from standardwebhooks import Webhook

from django_outbound_webhooks.delivery.send_webhook import send_webhook
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.rendered_body import RenderedBody

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()
BODY = RenderedBody(body=b'{"hello":"world"}', content_type="application/json")


def _client(handler: object) -> httpx2.Client:
    # httpx2's own MockTransport, not a mocking library. respx targets httpx and
    # would install a second HTTP client, so every assertion about the wire
    # would be made against the one this package does not use.
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _send(
    handler: object, lease_seconds: float = 30.0, history: list[object] | None = None
) -> DeliveryVerdict:
    with _client(handler) as client:
        return send_webhook(
            client=client,
            url="https://example.test/hooks",
            secrets=[SECRET],
            message_id="msg_1",
            body=BODY,
            lease_seconds=lease_seconds,
            history=[] if history is None else history,
        ).verdict


def test_a_2xx_succeeds_on_the_first_attempt() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200)

    assert _send(handler) is DeliveryVerdict.SUCCEEDED
    assert len(seen) == 1


def test_what_goes_on_the_wire_verifies_against_the_specification() -> None:
    # The only assertion that means anything about conformance: hand the bytes
    # and headers the endpoint actually received to the specification's own
    # verifier, which is what a customer runs.
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200)

    _send(handler)
    request = seen[0]
    assert request.headers["content-type"] == "application/json"
    assert Webhook(SECRET).verify(request.content, dict(request.headers)) == {"hello": "world"}


def test_a_permanent_refusal_stops_immediately() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(410)

    assert _send(handler) is DeliveryVerdict.PERMANENT
    assert attempts == 1, "410 Gone must not be retried even once"


def test_a_transient_failure_is_retried_and_can_succeed() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(200 if attempts > 2 else 503)

    assert _send(handler) is DeliveryVerdict.SUCCEEDED
    assert attempts == 3


def test_a_transport_error_is_retried_rather_than_raised() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx2.ConnectError("refused")
        return httpx2.Response(200)

    assert _send(handler) is DeliveryVerdict.SUCCEEDED
    assert attempts == 2


def test_every_attempt_sends_byte_identical_content_under_one_id() -> None:
    # webhook-id is stable across attempts and is what a receiver deduplicates
    # on, so two different bodies under one id leave the customer in a state
    # that depends on which attempt landed.
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200 if len(seen) > 2 else 500)

    _send(handler)
    assert len({request.content for request in seen}) == 1
    assert {request.headers["webhook-id"] for request in seen} == {"msg_1"}


def test_the_timestamp_is_fresh_on_each_attempt() -> None:
    # The one thing that legitimately differs. Receivers verify the timestamp
    # against a tolerance window, so a retry that reused the original would be
    # rejected as too old.
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        time.sleep(1.1)
        return httpx2.Response(200 if len(seen) > 1 else 500)

    _send(handler)
    stamps = [request.headers["webhook-timestamp"] for request in seen]
    assert len(set(stamps)) == len(stamps)


def test_it_stops_before_the_lease_rather_than_after_it() -> None:
    # The failure this whole tier exists to prevent: an attempt that begins
    # inside the lease and finishes outside it, so the POST is sent and the
    # write that records it is rolled back by another worker.
    #
    # A short lease with the configured 10s timeout and 2s margin leaves an
    # 8s deadline; each attempt here is fast, so what stops it is elapsed time
    # rather than the endpoint.
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(503)

    started = time.monotonic()
    verdict = _send(handler, lease_seconds=13.0)
    elapsed = time.monotonic() - started

    assert verdict is DeliveryVerdict.RETRY
    assert attempts > 1, "it should have retried at least once inside the deadline"
    assert elapsed < 13.0 - 2.0, "the whole run must finish inside the lease, less the margin"


def test_a_lease_too_short_to_hold_one_request_is_refused() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200)

    with pytest.raises(ValueError, match="no room to retry"):
        _send(handler, lease_seconds=5.0)


def test_a_slow_attempt_cannot_push_the_run_past_the_lease(settings: object) -> None:
    """The property the whole inner tier exists for, driven rather than inspected.

    The instant-response test above does not distinguish stop_before_delay from
    stop_after_delay, because the overrun only appears when an attempt is slow
    enough to matter. Verified by mutation: swapping them leaves that test green
    and only the type assertion in test_retry_policy notices, which is a guard
    on the spelling rather than on the behaviour.

    Scaled down so it runs in seconds: a 1s timeout, a 0.5s margin and a 4s
    lease leave a 2.5s deadline, with each attempt taking 0.9s. Under
    stop_after_delay the last sleep lands at 3.3s and the attempt after it
    finishes past the lease; under stop_before_delay that sleep is refused.
    """
    settings.DJANGO_OUTBOUND_WEBHOOKS = {
        "TIMEOUT_SECONDS": 1.0,
        "LEASE_MARGIN_SECONDS": 0.5,
        "INNER_BACKOFF_BASE_SECONDS": 0.5,
    }
    lease, margin = 4.0, 0.5

    def handler(request: httpx2.Request) -> httpx2.Response:
        time.sleep(0.9)
        return httpx2.Response(503)

    started = time.monotonic()
    assert _send(handler, lease_seconds=lease) is DeliveryVerdict.RETRY
    elapsed = time.monotonic() - started

    assert elapsed <= lease - margin, (
        f"the run took {elapsed:.2f}s against a {lease}s lease with a {margin}s margin. "
        f"An attempt was started that could not finish in time, which is how a POST is sent "
        f"and the write recording it is rolled back by another worker."
    )
