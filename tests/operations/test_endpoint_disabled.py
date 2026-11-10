from __future__ import annotations

from django_domain_events import registry

from django_outbound_webhooks.delivery.delivery_targets import INTERNAL_EVENTS
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled


def test_it_is_declared_under_this_app_label() -> None:
    names = {entry.name for entry in registry.events()}
    assert "django_outbound_webhooks.EndpointDisabled" in names


def test_it_is_never_delivered_to_customer_endpoints() -> None:
    assert EndpointDisabled in INTERNAL_EVENTS


def test_an_operator_can_receive_it() -> None:
    # The whole reason it is an event: somebody else's code reacts to it.
    entry = next(e for e in registry.events() if e.event_class is EndpointDisabled)
    assert entry.event_class is EndpointDisabled
    assert set(EndpointDisabled.__dataclass_fields__) == {
        "endpoint_id",
        "endpoint_name",
        "dead_deliveries",
    }
