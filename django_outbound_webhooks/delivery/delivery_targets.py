from __future__ import annotations

import uuid

from django_domain_events import DeliveryContext

from django_outbound_webhooks.delivery.replay_target import replay_target
from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled
from django_outbound_webhooks.operations.endpoint_failing import EndpointFailing
from django_outbound_webhooks.operations.endpoint_recovered import EndpointRecovered
from django_outbound_webhooks.types.delivery_target import DeliveryTarget

#: This package's own events, which are never delivered to a customer endpoint,
#: whoever subscribes to them. The delivery receiver is a wildcard, so without
#: this it would be owed them like any other event.
#:
#: All three are about one endpoint's health, and the reason is the same for
#: each: the endpoint most obviously interested is the one failing, switched
#: off, or only just back - so every *other* customer subscribed would hear about
#: somebody else's integration, arriving signed, over their webhook. They are
#: for the operator's own receivers, which tell the customer through a channel
#: that is not the broken one.
#:
#: Written once, here, against the one receiver that delivers, rather than per
#: event: a new health event added without joining this list would be
#: delivered to every subscriber, which the tests check for each member.
INTERNAL_EVENTS: tuple[type, ...] = (EndpointDisabled, EndpointFailing, EndpointRecovered)


def delivery_targets(event: object, context: DeliveryContext) -> list[str]:
    """One target per endpoint owed this event, each carrying its frozen recipe."""
    if isinstance(event, INTERNAL_EVENTS):
        return []

    replaying = replay_target.get()
    if replaying is not None and replaying[0] == context.event_id:
        return [replaying[1].encode()]

    owed = endpoints_for(event_name=context.event_name, scope=context.scope)
    return [
        DeliveryTarget(
            endpoint_id=endpoint_id,
            format_name=format_name,
            format_version=format_version,
            message_id=str(uuid.uuid4()),
        ).encode()
        for endpoint_id, format_name, format_version in owed.values_list(
            "pk", "format_name", "format_version"
        )
    ]
