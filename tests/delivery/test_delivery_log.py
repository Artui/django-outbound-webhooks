"""The delivery log, and the half of it that only exists because of the hook."""

from __future__ import annotations

import base64
import hashlib
import logging

import httpx2
import pytest
from django.db import transaction
from django_domain_events import drain_outbox, fire

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fast_retries(settings: object) -> None:
    """Scale the retry budget down so a failing endpoint does not cost a minute.

    The defaults give the inner tier a 48 second deadline, which is right in
    production and unusable here: a test that drives four outer attempts against
    a failing endpoint would spend three minutes sleeping. The shape under test
    is the same at any scale -- these are the same three numbers, smaller.
    """
    settings.DJANGO_OUTBOUND_WEBHOOKS = {
        "DELIVERY_LEASE_SECONDS": 2,
        "TIMEOUT_SECONDS": 0.5,
        "LEASE_MARGIN_SECONDS": 0.2,
        "INNER_BACKOFF_BASE_SECONDS": 0.01,
    }


def _endpoint(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "event_names": ["testapp.OrderPlaced"],
    }
    fields.update(overrides)
    return register_endpoint(**fields)


def _answering(monkeypatch: pytest.MonkeyPatch, statuses: list[int]) -> list[httpx2.Request]:
    """Give the endpoint a scripted sequence of answers."""
    seen: list[httpx2.Request] = []
    remaining = list(statuses)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        status = remaining.pop(0) if remaining else statuses[-1]
        return httpx2.Response(status, text="nope" if status >= 400 else "ok")

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.deliver_due.webhook_client",
        lambda: httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return seen


def _fire_and_drain(times: int = 2) -> None:
    with transaction.atomic():
        fire(OrderPlaced(order_id=7, total_cents=2500))
    for _ in range(times):
        drain_outbox()


def test_a_successful_delivery_logs_one_row(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = _endpoint()
    _answering(monkeypatch, [200])
    _fire_and_drain()

    row = DeliveryAttempt.objects.get()
    assert row.endpoint_id == endpoint.pk
    assert row.url == "https://example.test/hooks"
    assert (row.outer_attempt, row.inner_attempt) == (1, 1)
    assert row.response_status == 200
    assert row.verdict == "succeeded"
    assert row.format_name == "envelope"


def test_a_failed_delivery_is_logged_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reason the substrate grew a failure hook.

    A receiver's writes are discarded the moment it raises, so before the hook
    this table would have held successes and nothing else -- which is the half
    an operator does not need.
    """
    _endpoint()
    _answering(monkeypatch, [410])
    _fire_and_drain()

    rows = list(DeliveryAttempt.objects.all())
    assert rows, "a failed delivery must reach the log at all"
    assert {row.response_status for row in rows} == {410}
    assert {row.verdict for row in rows} == {"permanent"}
    assert rows[0].response_body == "nope"


def test_a_permanent_refusal_still_costs_the_whole_outer_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The log makes a known gap visible, which is half of what a log is for.

    410 Gone stops the inner tier after one request, because a webhook's verdict
    is a return value and the policy can read it. The substrate can only retry
    what raises and cannot be told a failure is terminal, so it re-delivers to
    the attempt budget regardless: one request per outer attempt, five times,
    to an endpoint that has already said it is retired.

    That is the first of the findings this package owes back, and until it is
    fixed the log is where an operator can see it happening.
    """
    _endpoint()
    _answering(monkeypatch, [410])
    _fire_and_drain()

    rows = list(DeliveryAttempt.objects.all())
    assert [row.inner_attempt for row in rows] == [1] * len(rows), "the inner tier stopped at one"
    assert [row.outer_attempt for row in rows] == list(range(1, len(rows) + 1))
    assert len(rows) > 1, "and the substrate retried anyway, which is the gap"


def test_the_inner_attempts_of_one_delivery_are_all_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _endpoint()
    _answering(monkeypatch, [503, 503, 200])
    _fire_and_drain()

    rows = list(DeliveryAttempt.objects.all())
    assert [row.inner_attempt for row in rows] == [1, 2, 3]
    assert [row.outer_attempt for row in rows] == [1, 1, 1]
    assert [row.verdict for row in rows] == ["retry", "retry", "succeeded"]


def test_the_two_numbers_count_different_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    # They multiply rather than add. A log calling either of them "attempt"
    # would make every number in it ambiguous.
    _endpoint()
    _answering(monkeypatch, [500])
    _fire_and_drain(times=4)

    rows = list(DeliveryAttempt.objects.all())
    assert len({row.outer_attempt for row in rows}) > 1, "the substrate retried the delivery"
    assert max(row.inner_attempt for row in rows) > 1, "and each one retried its request"
    for row in rows:
        assert row.inner_attempt >= 1 and row.outer_attempt >= 1


def test_every_attempt_of_one_delivery_records_the_same_body_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The hash is what makes a re-render that disagrees with the signed original
    # a findable event rather than a customer-side mystery.
    _endpoint()
    seen = _answering(monkeypatch, [503, 503, 200])
    _fire_and_drain()

    hashes = {row.request_body_sha256 for row in DeliveryAttempt.objects.all()}
    assert len(hashes) == 1
    assert hashes == {hashlib.sha256(seen[0].content).hexdigest()}


def test_a_transport_error_records_the_error_and_no_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _endpoint()

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused")

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.deliver_due.webhook_client",
        lambda: httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    _fire_and_drain()

    row = DeliveryAttempt.objects.first()
    assert row is not None
    assert row.response_status is None
    assert "ConnectError" in row.error


def test_a_delivery_that_never_made_a_request_logs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A deleted endpoint, a pruned event, a format that was never published. The
    # substrate's own row already records those; an empty attempt row here would
    # invent a request that was never made.
    endpoint = _endpoint()
    _answering(monkeypatch, [200])
    Endpoint.objects.filter(pk=endpoint.pk).update(is_active=False)
    _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 0


def test_deleting_an_endpoint_keeps_its_history(monkeypatch: pytest.MonkeyPatch) -> None:
    # A log whose rows disappear with the thing they are evidence about is not
    # a log. The URL is denormalised for the same reason.
    endpoint = _endpoint()
    _answering(monkeypatch, [200])
    _fire_and_drain()
    endpoint.delete()

    row = DeliveryAttempt.objects.get()
    assert row.endpoint_id is None
    assert row.url == "https://example.test/hooks"


def test_str_names_the_delivery_and_both_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    _endpoint()
    _answering(monkeypatch, [200])
    _fire_and_drain()

    row = DeliveryAttempt.objects.get()
    assert str(row) == f"{row.message_id} 1.1 -> 200"


def test_a_response_body_is_truncated(monkeypatch: pytest.MonkeyPatch, settings: object) -> None:
    settings.DJANGO_OUTBOUND_WEBHOOKS = {
        **settings.DJANGO_OUTBOUND_WEBHOOKS,
        "LOG_BODY_CHARS": 10,
    }
    _endpoint()

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, text="x" * 5000)

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.deliver_due.webhook_client",
        lambda: httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    _fire_and_drain()

    row = DeliveryAttempt.objects.first()
    assert row is not None
    assert len(row.response_body) == 10


def test_a_failure_before_any_request_logs_nothing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The failure path's own version of "no request was made".

    A pruned source event, a format that was never published: the delivery
    raises before the first POST, so the hook runs with nothing to write. The
    substrate's own row already records why, and an empty attempt row here would
    invent a request that never happened.
    """
    endpoint = _endpoint()
    _answering(monkeypatch, [200])

    # Pin the endpoint to a version nothing published, past register_endpoint's
    # validation. The fan-out freezes it onto the delivery and the delivery then
    # fails closed at render time, before any request.
    Endpoint.objects.filter(pk=endpoint.pk).update(format_version=9)
    with caplog.at_level(logging.ERROR):
        _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 0
    # And the hook did not blow up getting there. The substrate swallows a
    # raising hook by design, so "no rows" alone is satisfied both by the guard
    # working and by the hook crashing on the way in -- which is how a bug here
    # would stay invisible. Only the absence of that log line separates them.
    assert "on_failure hook" not in caplog.text


def test_the_stash_does_not_leak_between_deliveries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both paths clear it, so a delivery that raises before setting it cannot
    # inherit the previous one's attempts and log them against the wrong id.
    from django_outbound_webhooks.delivery.pending_attempts import pending_attempts

    _endpoint()
    _answering(monkeypatch, [200])
    _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 1
    assert pending_attempts.get() is None
