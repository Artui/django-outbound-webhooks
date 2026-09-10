"""Turn one domain event into one delivery per subscribed endpoint."""

from __future__ import annotations

import uuid

from django_domain_events import DeliveryContext, fire

from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for


def fan_out(event: object, context: DeliveryContext) -> None:
    """Fire one ``WebhookDeliveryDue`` for every endpoint owed this event.

    Runs as a durable receiver, so it runs exactly as reliably as anything else
    the substrate delivers: the rows it writes commit with its own
    acknowledgement, and if the process dies first the whole thing is retried
    rather than half-done.

    The endpoint's format is read here and frozen onto the fired event. Reading
    it at delivery time instead would let an operator's edit change what an
    already-integrated consumer receives on a retry, under a signature that
    still verifies.

    ``endpoints_for`` is the isolation boundary rather than a lookup, and it
    fails closed on an event whose scope carries no tenant. That case is not
    exotic -- an event fired by a management command, or by anything that forgot
    to open an ``attributed()`` block, arrives with an empty scope.
    """
    for endpoint in endpoints_for(event_name=context.event_name, scope=context.scope):
        fire(
            WebhookDeliveryDue(
                endpoint_id=endpoint.pk,
                source_event_id=context.event_id,
                format_name=endpoint.format_name,
                format_version=endpoint.format_version,
                # uuid4 rather than anything derived from the ids. A derived id
                # would repeat if an operator ever replayed the source event,
                # and a receiver that deduplicates would then silently drop the
                # replay it was asked for.
                message_id=str(uuid.uuid4()),
            )
        )
