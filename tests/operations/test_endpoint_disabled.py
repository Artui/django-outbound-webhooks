"""The event auto-disable fires, and who is not sent it."""

from __future__ import annotations

from django_domain_events import registry

from django_outbound_webhooks.delivery.register_fan_out import INTERNAL_EVENTS, KEY_PREFIX
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled


def test_it_is_declared_under_this_app_label() -> None:
    # The name is what a receiver in somebody else's app declares itself
    # against, and what a stored event row carries, so it is part of the
    # contract rather than an implementation detail.
    names = {entry.name for entry in registry.events()}
    assert "django_outbound_webhooks.EndpointDisabled" in names


def test_it_is_not_fanned_out_to_customer_endpoints() -> None:
    # Reads like an omission and is the opposite: the endpoint most obviously
    # interested has just been switched off, so a customer subscribed to this
    # would only ever hear about other people's endpoints failing.
    assert EndpointDisabled in INTERNAL_EVENTS
    keys = {entry.key for entry in registry.receivers()}
    assert f"{KEY_PREFIX}.django_outbound_webhooks.EndpointDisabled" not in keys


def test_an_operator_can_receive_it() -> None:
    # The whole reason it is an event: somebody else's code reacts to it. A
    # receiver is declared against the class, which is why the class is
    # importable by leaf path even though the package root cannot re-export it.
    entry = next(e for e in registry.events() if e.event_class is EndpointDisabled)
    assert entry.event_class is EndpointDisabled
    assert set(EndpointDisabled.__dataclass_fields__) == {
        "endpoint_id",
        "endpoint_name",
        "dead_deliveries",
    }
