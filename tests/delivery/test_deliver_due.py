"""Delivering one endpoint's copy, and the four ways it does not."""

from __future__ import annotations

import base64

import httpx2
import pytest
from django.db import transaction
from django_domain_events import drain_outbox, fire
from django_domain_events.models.event_record import EventRecord
from standardwebhooks import Webhook

from django_outbound_webhooks.delivery.deliver_due import DeliveryFailed, deliver_due
from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.endpoint import Endpoint
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


class _Context:
    """The substrate hands receivers a DeliveryContext; only attempt is read."""

    attempt = 1
    event_id = 0
    event_name = ""
    actor_key = ""
    actor_label = ""
    scope: dict[str, object] = {}


def _endpoint(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "event_names": ["testapp.OrderPlaced"],
    }
    fields.update(overrides)
    return register_endpoint(**fields)


def _source() -> EventRecord:
    with transaction.atomic():
        fire(OrderPlaced(order_id=7, total_cents=2500))
    return EventRecord.objects.get(name="testapp.OrderPlaced")


def _due(endpoint: Endpoint, source: EventRecord, **overrides: object) -> WebhookDeliveryDue:
    fields: dict[str, object] = {
        "endpoint_id": endpoint.pk,
        "source_event_id": source.pk,
        "format_name": "envelope",
        "format_version": 1,
        "message_id": "msg_1",
    }
    fields.update(overrides)
    return WebhookDeliveryDue(**fields)


def test_it_posts_a_body_the_specification_verifies(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    deliver_due(_due(endpoint, source), _Context())

    assert len(no_real_network) == 1
    request = no_real_network[0]
    assert str(request.url) == "https://example.test/hooks"
    document = Webhook(SECRET).verify(request.content, dict(request.headers))
    assert document["type"] == "testapp.OrderPlaced"
    assert document["data"]["order_id"] == 7
    assert request.headers["webhook-id"] == "msg_1"


def test_a_deactivated_endpoint_is_not_posted_to_and_does_not_raise(
    no_real_network: list[httpx2.Request],
) -> None:
    # The customer switched it off. Raising would retry a destination they
    # removed on purpose; returning is what says nothing is owed.
    endpoint, source = _endpoint(), _source()
    Endpoint.objects.filter(pk=endpoint.pk).update(is_active=False)
    deliver_due(_due(endpoint, source), _Context())
    assert no_real_network == []


def test_a_deleted_endpoint_is_not_posted_to_and_does_not_raise(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    due = _due(endpoint, source)
    endpoint.delete()
    deliver_due(due, _Context())
    assert no_real_network == []


def test_a_pruned_source_event_raises_rather_than_returning(
    no_real_network: list[httpx2.Request],
) -> None:
    # The opposite call from the two above, and the reason is the difference
    # between "nothing is owed" and "something is owed and can never be paid".
    # Retention outrunning delivery has to be visible.
    endpoint, source = _endpoint(), _source()
    due = _due(endpoint, source)
    source.delete()
    with pytest.raises(DeliveryFailed, match="no longer in the log"):
        deliver_due(due, _Context())
    assert no_real_network == []


def test_a_format_version_that_was_never_published_fails_closed(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    with pytest.raises(LookupError, match="envelope@9"):
        deliver_due(_due(endpoint, source, format_version=9), _Context())
    assert no_real_network == []


def test_a_refusal_raises_so_the_substrate_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Raising is the only thing the substrate reads. It cannot be told a failure
    # is terminal, so a permanent verdict still burns the attempt budget before
    # dead-lettering: wasteful, correct in the end, and the first finding this
    # package owes back.
    def factory() -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(lambda request: httpx2.Response(410)))

    monkeypatch.setattr("django_outbound_webhooks.delivery.deliver_due.webhook_client", factory)
    endpoint, source = _endpoint(), _source()
    with pytest.raises(DeliveryFailed, match="permanent"):
        deliver_due(_due(endpoint, source), _Context())


def test_end_to_end_a_fired_event_reaches_the_endpoint(
    no_real_network: list[httpx2.Request],
) -> None:
    # The composed path, which is the only place the fan-out and the delivery
    # are exercised as one thing: fire, drain, and a stranger's server has the
    # bytes.
    _endpoint()
    with transaction.atomic():
        fire(OrderPlaced(order_id=99, total_cents=4200))
    drain_outbox()
    drain_outbox()

    assert len(no_real_network) == 1
    document = Webhook(SECRET).verify(no_real_network[0].content, dict(no_real_network[0].headers))
    assert document["data"]["order_id"] == 99
