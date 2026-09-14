"""Attaching the fan-out to every declared event."""

from __future__ import annotations

from django_domain_events import registry

from django_outbound_webhooks.delivery.register_fan_out import (
    INTERNAL_EVENTS,
    KEY_PREFIX,
    register_fan_out,
)
from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled


def test_every_declared_event_has_one() -> None:
    # Registered at ready(), so this reads the live registry rather than calling
    # register_fan_out again: what matters is the state the app left behind.
    covered = {
        entry.key.removeprefix(f"{KEY_PREFIX}.")
        for entry in registry.receivers()
        if entry.key.startswith(f"{KEY_PREFIX}.")
    }
    assert {"testapp.OrderPlaced", "testapp.OrderShipped"} <= covered


def test_this_packages_own_events_are_not_fanned_out() -> None:
    # Two of them now, for two different reasons: fanning out the fan-out event
    # is an unbounded write loop, and fanning out EndpointDisabled tells every
    # customer about somebody else's broken integration.
    assert set(INTERNAL_EVENTS) == {WebhookDeliveryDue, EndpointDisabled}
    keys = {entry.key for entry in registry.receivers()}
    assert f"{KEY_PREFIX}.django_outbound_webhooks.WebhookDeliveryDue" not in keys
    assert f"{KEY_PREFIX}.django_outbound_webhooks.EndpointDisabled" not in keys


def test_the_keys_are_derived_from_the_event_name() -> None:
    # A delivery row addresses its receiver by key, so a key that depended on
    # load order would strand rows written before a restart.
    assert f"{KEY_PREFIX}.testapp.OrderPlaced" in {e.key for e in registry.receivers()}


def test_running_it_again_is_harmless() -> None:
    # Re-registering an identical receiver is what a double import looks like,
    # and the substrate tolerates it by comparing the whole record.
    before = {entry.key for entry in registry.receivers()}
    register_fan_out()
    assert {entry.key for entry in registry.receivers()} == before


def test_it_reports_what_it_registered() -> None:
    keys = register_fan_out()
    assert f"{KEY_PREFIX}.testapp.OrderPlaced" in keys
    assert all(event.__name__ not in key for key in keys for event in INTERNAL_EVENTS)
