"""The event fired when an endpoint's deliveries start dying."""

from __future__ import annotations

from django_domain_events import registry

from django_outbound_webhooks.delivery.delivery_targets import INTERNAL_EVENTS
from django_outbound_webhooks.operations.endpoint_failing import EndpointFailing


def test_it_is_declared_under_this_app_label() -> None:
    # The name is what an operator's receiver declares itself against and what
    # a stored row carries, so it is part of the contract.
    entry = registry.event_for_class(EndpointFailing)
    assert entry is not None
    assert entry.name == "django_outbound_webhooks.EndpointFailing"


def test_it_carries_what_a_notification_needs() -> None:
    assert set(EndpointFailing.__dataclass_fields__) == {
        "endpoint_id",
        "endpoint_name",
        "disabled_after_dead_deliveries",
    }


def test_it_is_never_delivered_to_customer_endpoints() -> None:
    # The behaviour, with a subscriber, is tested beside delivery_targets.
    assert EndpointFailing in INTERNAL_EVENTS
