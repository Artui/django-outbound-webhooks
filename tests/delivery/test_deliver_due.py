"""Delivering one endpoint's copy, and the three ways it does not."""

from __future__ import annotations

import base64

import httpx2
import pytest
from django.db import transaction
from django_domain_events import DeliveryContext, drain_outbox, fire
from django_domain_events.models.event_record import EventRecord
from standardwebhooks import Webhook

from django_outbound_webhooks.delivery.deliver_due import DeliveryFailed, deliver_due
from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.types.delivery_target import DeliveryTarget
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


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


def _context(endpoint: Endpoint, source: EventRecord, **overrides: object) -> DeliveryContext:
    """The context the substrate hands the receiver, built the way it builds it:
    off the event row, with the target the row was written with."""
    fields: dict[str, object] = {
        "endpoint_id": endpoint.pk,
        "format_name": "envelope",
        "format_version": 1,
        "message_id": "msg_1",
    }
    fields.update(overrides)
    return DeliveryContext(
        event_id=source.pk,
        event_name=source.name,
        attempt=1,
        actor_key="",
        actor_label="",
        scope={},
        target=DeliveryTarget(**fields).encode(),
    )


EVENT = OrderPlaced(order_id=7, total_cents=2500)


def test_it_posts_a_body_the_specification_verifies(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    deliver_due(EVENT, _context(endpoint, source))

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
    deliver_due(EVENT, _context(endpoint, source))
    assert no_real_network == []


def test_a_deleted_endpoint_is_not_posted_to_and_does_not_raise(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    context = _context(endpoint, source)
    endpoint.delete()
    deliver_due(EVENT, context)
    assert no_real_network == []


def test_a_format_version_that_was_never_published_fails_closed(
    no_real_network: list[httpx2.Request],
) -> None:
    endpoint, source = _endpoint(), _source()
    with pytest.raises(LookupError, match="envelope@9"):
        deliver_due(EVENT, _context(endpoint, source, format_version=9))
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
        deliver_due(EVENT, _context(endpoint, source))


def test_end_to_end_a_fired_event_reaches_the_endpoint(
    no_real_network: list[httpx2.Request],
) -> None:
    # The composed path, which is the only place the targets callable and the
    # delivery are exercised as one thing: fire, drain once, and a stranger's
    # server has the bytes. One drain, because there is no second hop.
    _endpoint()
    with transaction.atomic():
        fire(OrderPlaced(order_id=99, total_cents=4200))
    drain_outbox()

    assert len(no_real_network) == 1
    document = Webhook(SECRET).verify(no_real_network[0].content, dict(no_real_network[0].headers))
    assert document["data"]["order_id"] == 99


def test_the_pinned_format_decides_the_body_and_the_content_type(
    no_real_network: list[httpx2.Request],
) -> None:
    """The seam, end to end: a second format changes the wire and nothing else.

    Everything between rendering and sending is format-blind -- the signature
    is over whatever bytes came back, and the content type travels with them
    rather than being fixed by the sender. That is easy to write and easy to
    get wrong in a way only a second format can show, because with one format
    a hardcoded `application/json` is indistinguishable from a read.
    """
    endpoint, source = _endpoint(), _source()
    deliver_due(EVENT, _context(endpoint, source, format_name="cloudevents", format_version=1))

    request = no_real_network[0]
    assert request.headers["content-type"] == "application/cloudevents+json; charset=UTF-8"
    document = Webhook(SECRET).verify(request.content, dict(request.headers))
    assert document["specversion"] == "1.0"
    assert document["source"] == "https://shop.example/events"
    assert document["type"] == "testapp.OrderPlaced"
    assert document["data"]["order_id"] == 7
