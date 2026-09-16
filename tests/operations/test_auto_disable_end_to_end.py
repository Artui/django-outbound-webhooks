"""Auto-disable driven by real deliveries rather than by calling the counter.

Mirrors the feature rather than one module, like the delivery-log tests: the
wiring is what is under test here, and it is spread across the receiver's
success path, the substrate's failure hook and the two counters. Each of those
is unit-tested beside its own source; what only this file can show is that a
delivery failing for real reaches them.
"""

from __future__ import annotations

import base64

import httpx2
import pytest
from django.db import transaction
from django_domain_events import drain_outbox, fire
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.endpoint import Endpoint
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fast_retries(settings: object) -> None:
    """Retry budgets scaled down, and a threshold small enough to reach.

    The same three numbers as production, smaller: a test that drives a whole
    attempt budget against a failing endpoint at the real deadline would spend
    minutes asleep. The threshold is two so that "not before" and "on" are both
    assertable in one run.
    """
    settings.DJANGO_OUTBOUND_WEBHOOKS = {
        "DELIVERY_LEASE_SECONDS": 2,
        "TIMEOUT_SECONDS": 0.5,
        "LEASE_MARGIN_SECONDS": 0.2,
        "INNER_BACKOFF_BASE_SECONDS": 0.01,
        "AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 2,
    }


def _answering(monkeypatch: pytest.MonkeyPatch, status: int) -> list[httpx2.Request]:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(status, text="nope" if status >= 400 else "ok")

    def factory() -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(handler))

    monkeypatch.setattr("django_outbound_webhooks.delivery.deliver_due.webhook_client", factory)
    return seen


def _endpoint() -> Endpoint:
    return register_endpoint(
        name="Acme production",
        url="https://example.test/hooks",
        secret=SECRET,
        event_names=["testapp.OrderPlaced"],
    )


def _fire_and_drain(times: int = 12) -> None:
    with transaction.atomic():
        fire(OrderPlaced(order_id=7, total_cents=2500))
    # Drained repeatedly: each pass is one outer attempt, and the passes burn the
    # delivery's attempt budget until the substrate declares it dead.
    for _ in range(times):
        drain_outbox()


def test_a_delivery_that_dies_for_real_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    _answering(monkeypatch, 500)
    endpoint = _endpoint()
    _fire_and_drain()

    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 1
    assert endpoint.is_active is True


def test_the_second_one_switches_the_endpoint_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _answering(monkeypatch, 500)
    endpoint = _endpoint()
    _fire_and_drain()
    _fire_and_drain()

    endpoint.refresh_from_db()
    assert endpoint.is_active is False
    assert endpoint.disabled_at is not None
    assert EventRecord.objects.filter(name="django_outbound_webhooks.EndpointDisabled").count() == 1


def test_a_delivery_that_lands_clears_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # The half that makes the threshold mean "sustained". Without it an endpoint
    # that fails once a month is disabled in the end, and the test that would
    # have caught that is this one rather than any unit test of the counter.
    _answering(monkeypatch, 500)
    endpoint = _endpoint()
    _fire_and_drain()
    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 1

    _answering(monkeypatch, 200)
    _fire_and_drain(times=2)

    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 0
    assert endpoint.is_active is True
