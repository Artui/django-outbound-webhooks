"""One fired event becoming one delivery row per subscribed endpoint.

What is asserted is the rows the substrate wrote - how many, and the target each
carries - rather than that a POST happened, because a round trip through the
receiver would pass for a design that delivered once to everybody.
"""

from __future__ import annotations

import base64
import sys
from collections.abc import Iterator

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext, override_settings
from django_domain_events import DeliveryContext, attributed, drain_outbox, fire, registry
from django_domain_events.models.delivery_record import DeliveryRecord

from django_outbound_webhooks.delivery.deliver_due import RECEIVER_KEY
from django_outbound_webhooks.delivery.delivery_targets import INTERNAL_EVENTS, delivery_targets
from django_outbound_webhooks.delivery.replay_target import replay_target
from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for
from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled
from django_outbound_webhooks.types.delivery_target import DeliveryTarget
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


def _fire(event: object) -> int:
    with transaction.atomic():
        event_id = fire(event)
    assert event_id is not None
    return event_id


def _targets(event_id: int) -> list[DeliveryTarget]:
    """The delivery rows the substrate wrote for this receiver, decoded."""
    return [
        DeliveryTarget.decode(target)
        for target in DeliveryRecord.objects.filter(event_id=event_id, receiver_key=RECEIVER_KEY)
        .order_by("pk")
        .values_list("target", flat=True)
    ]


def test_a_subscribed_endpoint_gets_one_delivery_row() -> None:
    endpoint = _endpoint()
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))

    [target] = _targets(event_id)
    assert target.endpoint_id == endpoint.pk
    row = DeliveryRecord.objects.get(event_id=event_id, receiver_key=RECEIVER_KEY)
    assert (row.status, row.attempts) == ("pending", 0)


def test_each_subscribed_endpoint_gets_its_own_row() -> None:
    """The whole point: each row has its own attempt count, backoff and
    dead-letter, so one rotted endpoint cannot drag the others."""
    first = _endpoint("Acme")
    second = _endpoint("Globex", url="https://other.test/hooks")
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))

    assert sorted(t.endpoint_id for t in _targets(event_id)) == sorted([first.pk, second.pk])
    assert DeliveryRecord.objects.filter(event_id=event_id).count() == 2


def test_an_endpoint_subscribed_to_something_else_gets_nothing() -> None:
    _endpoint(event_names=["testapp.OrderShipped"])
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))
    assert _targets(event_id) == []


def test_an_event_nobody_subscribes_to_writes_no_row_at_all() -> None:
    """A wildcard receiver is owed every event; returning no targets is what
    keeps the delivery table from growing a row per event in the system."""
    _endpoint()
    event_id = _fire(OrderShipped(order_id=1))
    assert DeliveryRecord.objects.filter(event_id=event_id).count() == 0


def test_the_event_reaches_only_its_own_tenants_endpoints(settings: object) -> None:
    """The isolation boundary, through fire() rather than beside it.

    ``endpoints_for`` is tested on its own; what only this can show is that the
    scope the event was fired under is the scope the boundary is handed. Two
    tenants subscribed to the same event, so a callable that dropped the scope
    would either send to both or - failing closed - to neither.
    """
    settings.DJANGO_OUTBOUND_WEBHOOKS = {
        **settings.DJANGO_OUTBOUND_WEBHOOKS,
        "TENANT_SCOPE_KEY": "tenant",
    }
    acme = _endpoint("Acme", tenant="acme")
    _endpoint("Globex", tenant="globex", url="https://other.test/hooks")

    with transaction.atomic(), attributed(tenant="acme"):
        event_id = fire(OrderPlaced(order_id=1, total_cents=100))
    assert [t.endpoint_id for t in _targets(event_id)] == [acme.pk]

    unscoped = _fire(OrderPlaced(order_id=2, total_cents=100))
    assert DeliveryRecord.objects.filter(event_id=unscoped).count() == 0


def test_the_message_id_is_unique_per_delivery() -> None:
    # A receiver deduplicates on webhook-id, so two customers sharing one would
    # mean the second silently dropping a delivery it should have taken.
    _endpoint("Acme")
    _endpoint("Globex", url="https://other.test/hooks")
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))

    ids = [target.message_id for target in _targets(event_id)]
    assert len(set(ids)) == len(ids) == 2


def test_the_format_is_frozen_when_the_event_is_fired() -> None:
    # An operator editing an endpoint's pin between the first attempt and a
    # retry must not change what an already-integrated consumer receives, under
    # a signature that still verifies.
    endpoint = _endpoint()
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))
    Endpoint.objects.filter(pk=endpoint.pk).update(format_name="cloudevents", format_version=9)

    [target] = _targets(event_id)
    assert (target.format_name, target.format_version) == ("envelope", 1)


def test_the_frozen_format_is_the_endpoints_own(second_format: FormatId) -> None:
    """The one above cannot tell a read from a hardcoded default, since every
    other endpoint in the suite is pinned to the same format."""
    _endpoint("Acme", format_name=second_format.name, format_version=second_format.version)
    event_id = _fire(OrderPlaced(order_id=1, total_cents=100))

    [target] = _targets(event_id)
    assert (target.format_name, target.format_version) == (
        second_format.name,
        second_format.version,
    )


def test_this_packages_own_event_is_never_delivered_even_to_a_subscriber() -> None:
    """Sized so the exclusion is what answers.

    The endpoint really is subscribed to the internal event, and the tenant
    boundary really would match it - the precondition says so - so an empty
    result can only come from the exclusion and not from nobody subscribing.
    """
    name = "django_outbound_webhooks.EndpointDisabled"
    endpoint = _endpoint(event_names=[name])
    assert list(endpoints_for(event_name=name, scope={})) == [endpoint]

    event_id = _fire(EndpointDisabled(endpoint_id=1, endpoint_name="x", dead_deliveries=20))

    assert DeliveryRecord.objects.filter(event_id=event_id).count() == 0


def test_the_internal_events_are_exactly_this_packages_own() -> None:
    names = {entry.name for entry in registry.events() if entry.event_class in INTERNAL_EVENTS}
    assert names == {"django_outbound_webhooks.EndpointDisabled"}


def test_the_lookup_is_one_query_per_fired_event() -> None:
    """The cost the targets callable adds to every write in the deployment.

    It runs inside the caller's transaction on every fired event, so the claim
    that it is one lookup is a claim about somebody else's hot path.
    """
    _endpoint("Acme")
    _endpoint("Globex", url="https://other.test/hooks")
    context = DeliveryContext(
        event_id=1,
        event_name="testapp.OrderPlaced",
        attempt=1,
        actor_key="",
        actor_label="",
        scope={},
    )
    with CaptureQueriesContext(connection) as queries:
        targets = delivery_targets(OrderPlaced(order_id=1, total_cents=100), context)

    assert len(targets) == 2
    assert len(queries.captured_queries) == 1


def test_an_internal_event_costs_no_query_at_all() -> None:
    context = DeliveryContext(
        event_id=1,
        event_name="django_outbound_webhooks.EndpointDisabled",
        attempt=1,
        actor_key="",
        actor_label="",
        scope={},
    )
    with CaptureQueriesContext(connection) as queries:
        assert delivery_targets(EndpointDisabled(1, "x", 20), context) == []
    assert queries.captured_queries == []


def test_a_replay_target_left_behind_does_not_redirect_another_event() -> None:
    """Tied to one event id, so a value that outlived its replay cannot send
    every later event to one customer's endpoint."""
    acme = _endpoint("Acme")
    globex = _endpoint("Globex", url="https://other.test/hooks")
    stray = DeliveryTarget(
        endpoint_id=globex.pk, format_name="envelope", format_version=1, message_id="stray"
    )
    token = replay_target.set((-1, stray))
    try:
        event_id = _fire(OrderPlaced(order_id=1, total_cents=100))
    finally:
        replay_target.reset(token)

    targets = _targets(event_id)
    assert sorted(t.endpoint_id for t in targets) == sorted([acme.pk, globex.pk])
    assert "stray" not in {t.message_id for t in targets}


@pytest.fixture
def _late_app_cleanup() -> Iterator[None]:
    """Put back what installing an app mid-test disturbs.

    Installing an app re-runs every app's ``ready()``, and this package's
    publishes the built-in formats as fresh objects, which the format registry
    refuses over the ones already published. So the test sets the registry
    aside just before installing the app, and this restores it after, along with
    the late event and its module.
    """
    published = dict(formats._formats)
    try:
        yield
    finally:
        formats._formats.clear()
        formats._formats.update(published)
        late = registry.event_for_name("lateapp.LateArrival")
        if late is not None:
            registry._events_by_name.pop("lateapp.LateArrival")
            registry._events_by_class.pop(late.event_class)
        sys.modules.pop("tests.lateapp.events", None)


def test_an_event_declared_by_an_app_that_loads_later_reaches_its_endpoints(
    _late_app_cleanup: None, no_real_network: list[object]
) -> None:
    """What a registry walk at startup could never do, through real app loading.

    The receiver was declared in this package's ready(). Only then is
    ``tests.lateapp`` installed, so its event is declared by the substrate's
    autodiscovery afterwards - which the precondition pins.
    """
    assert registry.event_for_name("lateapp.LateArrival") is None
    endpoint = _endpoint(event_names=["lateapp.LateArrival"])

    formats._formats.clear()
    with override_settings(INSTALLED_APPS=[*settings.INSTALLED_APPS, "tests.lateapp"]):
        late = registry.event_for_name("lateapp.LateArrival")
        assert late is not None
        event_id = _fire(late.event_class(value=3))

        [target] = _targets(event_id)
        assert target.endpoint_id == endpoint.pk
        drain_outbox()

    assert len(no_real_network) == 1
