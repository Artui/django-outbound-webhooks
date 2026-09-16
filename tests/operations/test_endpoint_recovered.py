"""The event fired when a failing endpoint delivers again."""

from __future__ import annotations

from django_domain_events import registry

from django_outbound_webhooks.delivery.delivery_targets import INTERNAL_EVENTS
from django_outbound_webhooks.operations.endpoint_recovered import EndpointRecovered


def test_it_is_declared_under_this_app_label() -> None:
    entry = registry.event_for_class(EndpointRecovered)
    assert entry is not None
    assert entry.name == "django_outbound_webhooks.EndpointRecovered"


def test_it_carries_what_a_notification_needs() -> None:
    assert set(EndpointRecovered.__dataclass_fields__) == {"endpoint_id", "endpoint_name"}


def test_it_is_never_delivered_to_customer_endpoints() -> None:
    assert EndpointRecovered in INTERNAL_EVENTS
