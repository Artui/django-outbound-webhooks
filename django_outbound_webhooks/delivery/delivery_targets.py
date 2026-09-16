"""Which endpoints one fired event is owed to."""

from __future__ import annotations

import uuid

from django_domain_events import DeliveryContext

from django_outbound_webhooks.delivery.replay_target import replay_target
from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled
from django_outbound_webhooks.types.delivery_target import DeliveryTarget

#: This package's own events, which are never delivered to a customer endpoint,
#: whoever subscribes to them. The delivery receiver is a wildcard, so without
#: this it would be owed them like any other event.
#:
#: ``EndpointDisabled`` is the reason the list exists: the endpoint most
#: obviously interested in it has just been switched off, so every customer
#: subscribed to it would hear only about *other* customers' integrations
#: failing - somebody else's operational detail, arriving signed, over their
#: webhook.
INTERNAL_EVENTS: tuple[type, ...] = (EndpointDisabled,)


def delivery_targets(event: object, context: DeliveryContext) -> list[str]:
    """One target per endpoint owed this event, each carrying its frozen recipe.

    The delivery receiver's ``targets=``. The substrate calls it **at fire time,
    inside the transaction that fired the event**, and writes a delivery row per
    string it returns - so each endpoint has its own attempt count, backoff,
    dead-letter and replay, and a rotted endpoint cannot drag the others through
    its retries. Returning nothing writes no row at all.

    Two consequences of where it runs, and both are the design rather than
    accidents of it:

    - **It is a query in the hot path.** Every event the deployment fires reaches
      this, because the receiver is a wildcard. The internal events are ruled
      out before any query; everything else costs the one indexed lookup in
      ``endpoints_for``. That replaces what used to be a second event row, a
      second delivery row and a second relay pass per endpoint.
    - **If it raises, the caller's change rolls back.** A delivery that silently
      went to nobody would be worse. The query is a read against this package's
      own tables and does not raise in normal operation.

    ``endpoints_for`` is the tenant boundary, and it fails closed on an event
    whose scope carries no tenant.
    """
    if isinstance(event, INTERNAL_EVENTS):
        return []

    replaying = replay_target.get()
    if replaying is not None and replaying[0] == context.event_id:
        # One logged delivery being sent again, to the endpoint the log names.
        # Not re-matched through endpoints_for, as a replay never has been: it
        # goes where the original went, which already passed the boundary.
        return [replaying[1].encode()]

    owed = endpoints_for(event_name=context.event_name, scope=context.scope)
    return [
        DeliveryTarget(
            endpoint_id=endpoint_id,
            format_name=format_name,
            format_version=format_version,
            # Random rather than derived, so a replay can never repeat it: a
            # receiver deduplicating on webhook-id would silently drop the
            # replay it was asked for.
            message_id=str(uuid.uuid4()),
        ).encode()
        for endpoint_id, format_name, format_version in owed.values_list(
            "pk", "format_name", "format_version"
        )
    ]
