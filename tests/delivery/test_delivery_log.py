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
    """The reason the substrate grew a failure hook."""
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
    """The log makes a known gap visible, which is half of what a log is for."""
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
    # They multiply rather than add.
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
    # A deleted endpoint, a pruned event, a format that was never published.
    endpoint = _endpoint()
    _answering(monkeypatch, [200])
    Endpoint.objects.filter(pk=endpoint.pk).update(is_active=False)
    _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 0


def test_deleting_an_endpoint_keeps_its_history(monkeypatch: pytest.MonkeyPatch) -> None:
    # A log whose rows disappear with the thing they are evidence about is not a log.
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
    """The failure path's own version of "no request was made"."""
    endpoint = _endpoint()
    _answering(monkeypatch, [200])

    Endpoint.objects.filter(pk=endpoint.pk).update(format_version=9)
    with caplog.at_level(logging.ERROR):
        _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 0
    assert "on_failure hook" not in caplog.text


def test_the_stash_does_not_leak_between_deliveries(monkeypatch: pytest.MonkeyPatch) -> None:
    from django_outbound_webhooks.delivery.pending_attempts import pending_attempts

    _endpoint()
    _answering(monkeypatch, [200])
    _fire_and_drain()

    assert DeliveryAttempt.objects.count() == 1
    assert pending_attempts.get() is None
