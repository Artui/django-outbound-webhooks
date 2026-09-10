"""One domain event becoming one delivery per subscribed endpoint."""

from __future__ import annotations

import base64

import pytest
from django.db import transaction
from django_domain_events import drain_outbox, fire
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.types.format_id import FormatId
from tests.testapp.events import OrderPlaced, OrderShipped

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _endpoint(name: str = "Acme production", **overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": name,
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "event_names": ["testapp.OrderPlaced"],
    }
    fields.update(overrides)
    return register_endpoint(**fields)


def _due_events() -> list[EventRecord]:
    return list(
        EventRecord.objects.filter(name="django_outbound_webhooks.WebhookDeliveryDue").order_by(
            "pk"
        )
    )


def _fan_out(event: object) -> None:
    """Fire, then run only the fan-out, leaving the deliveries unsent.

    ``drain_outbox`` runs whatever is owed, so the delivery receiver would try
    to POST. Everything here is about what the fan-out *wrote*, so the endpoints
    are switched off first and the deliveries return without touching the wire.
    """
    with transaction.atomic():
        fire(event)
    drain_outbox()
    Endpoint.objects.update(is_active=False)
    drain_outbox()


def test_a_subscribed_endpoint_gets_one_delivery() -> None:
    endpoint = _endpoint()
    _fan_out(OrderPlaced(order_id=1, total_cents=100))

    due = _due_events()
    assert len(due) == 1
    assert due[0].payload["endpoint_id"] == endpoint.pk


def test_each_subscribed_endpoint_gets_its_own() -> None:
    # The whole reason for firing an event per endpoint rather than one delivery
    # covering all of them: each of these rows carries its own attempt count,
    # backoff and dead-letter, so one rotted endpoint cannot drag the others.
    first = _endpoint("Acme")
    second = _endpoint("Globex", url="https://other.test/hooks")
    _fan_out(OrderPlaced(order_id=1, total_cents=100))

    assert {row.payload["endpoint_id"] for row in _due_events()} == {first.pk, second.pk}


def test_an_endpoint_subscribed_to_something_else_gets_nothing() -> None:
    _endpoint(event_names=["testapp.OrderShipped"])
    _fan_out(OrderPlaced(order_id=1, total_cents=100))
    assert _due_events() == []


def test_an_event_nobody_subscribes_to_fans_out_to_nothing() -> None:
    _endpoint()
    _fan_out(OrderShipped(order_id=1))
    assert _due_events() == []


def test_the_message_id_is_unique_per_delivery() -> None:
    # A receiver deduplicates on webhook-id, so two customers sharing one would
    # mean the second silently dropping a delivery it should have taken.
    _endpoint("Acme")
    _endpoint("Globex", url="https://other.test/hooks")
    _fan_out(OrderPlaced(order_id=1, total_cents=100))

    ids = [row.payload["message_id"] for row in _due_events()]
    assert len(set(ids)) == len(ids) == 2


def test_the_format_is_frozen_at_fan_out_not_read_at_delivery() -> None:
    # An operator editing an endpoint's pin between the fan-out and a retry must
    # not change what an already-integrated consumer receives, under a signature
    # that still verifies.
    endpoint = _endpoint()
    _fan_out(OrderPlaced(order_id=1, total_cents=100))
    Endpoint.objects.filter(pk=endpoint.pk).update(format_name="cloudevents", format_version=9)

    due = _due_events()[0]
    assert due.payload["format_name"] == "envelope"
    assert due.payload["format_version"] == 1


def test_the_frozen_format_is_the_endpoints_own(second_format: FormatId) -> None:
    """The one above cannot tell a read from a hardcoded default.

    Found by mutation: replacing ``endpoint.format_name`` with the literal
    ``"envelope"`` left the whole suite green, because every endpoint in it was
    pinned to that one format. A fixture with a single candidate cannot hold the
    thing the test claims to check.
    """
    _endpoint("Acme", format_name=second_format.name, format_version=second_format.version)
    _fan_out(OrderPlaced(order_id=1, total_cents=100))

    due = _due_events()[0]
    assert due.payload["format_name"] == second_format.name
    assert due.payload["format_version"] == second_format.version


def test_the_delivery_records_which_event_it_carries() -> None:
    _endpoint()
    with transaction.atomic():
        source_id = fire(OrderPlaced(order_id=1, total_cents=100))
    drain_outbox()
    Endpoint.objects.update(is_active=False)
    drain_outbox()

    assert _due_events()[0].payload["source_event_id"] == source_id


def test_the_fan_out_event_does_not_fan_out_to_itself() -> None:
    # Not a tidy-up. A fan-out receiver on WebhookDeliveryDue would fire one per
    # endpoint for every delivery, each of which would fan out again: an
    # unbounded, committing write loop with the first generation already sent.
    _endpoint()
    _fan_out(OrderPlaced(order_id=1, total_cents=100))
    assert len(_due_events()) == 1
