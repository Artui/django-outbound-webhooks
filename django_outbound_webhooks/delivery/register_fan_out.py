"""Attach the fan-out receiver to every declared event."""

from __future__ import annotations

from django_domain_events import receiver, registry

from django_outbound_webhooks.delivery.fan_out import fan_out
from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled

#: Prefix for the receiver keys this registers. A delivery row addresses its
#: receiver by key, so the keys have to be stable across restarts and derived
#: from the event name rather than from anything about load order.
KEY_PREFIX = "django_outbound_webhooks.fan_out"

#: This package's own events, which are never fanned out to customer endpoints.
#: Read by the system check too, so that "every declared event has a fan-out
#: receiver" and "every declared event should have one" cannot drift apart.
INTERNAL_EVENTS = (WebhookDeliveryDue, EndpointDisabled)


def register_fan_out() -> list[str]:
    """Register one fan-out receiver per declared event, and name them.

    Walking the registry is the only spelling available. A package that is a
    *transport* wants to receive every event, and the substrate has no wildcard:
    ``receivers_for`` matches one event class at a time. So this runs from
    ``AppConfig.ready()`` and registers a receiver per class.

    That makes it sensitive to app load order, and the failure is silent: an
    event declared by an app that loads after this one gets no fan-out receiver
    and is simply never delivered to any endpoint. Nothing raises. The system
    check in ``checks.py`` is what turns that into something an operator sees,
    because it runs once every app is ready.

    ``INTERNAL_EVENTS`` are skipped, and neither is a tidy-up. Fanning out the
    fan-out event would fire one per endpoint for every delivery, each of which
    would fan out again: an unbounded write loop, committing, with the first
    generation already delivered. Fanning out ``EndpointDisabled`` would tell
    every *other* customer's endpoint that somebody's integration broke, while
    the one endpoint the event is about has just been switched off and is the
    one destination guaranteed not to receive it.

    Returns the keys it registered so a caller can see what happened; nothing in
    the package depends on the return value.
    """
    keys = []
    for entry in registry.events():
        if entry.event_class in INTERNAL_EVENTS:
            continue
        key = f"{KEY_PREFIX}.{entry.name}"
        receiver(entry.event_class, key=key, takes_context=True)(fan_out)
        keys.append(key)
    return keys
