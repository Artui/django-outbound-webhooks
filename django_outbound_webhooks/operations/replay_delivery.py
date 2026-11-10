from __future__ import annotations

import uuid

from django_domain_events import registry, replay_events
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.delivery.deliver_due import RECEIVER_KEY
from django_outbound_webhooks.delivery.replay_target import replay_target
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.types.delivery_target import DeliveryTarget


class ReplayRefused(Exception):
    """A delivery cannot be replayed, and the message says what is missing."""


def replay_delivery(*, message_id: str) -> str:
    """Fire a fresh delivery of a logged one, and return its new ``webhook-id``."""
    attempt = (
        DeliveryAttempt.objects.select_related("endpoint")
        .filter(message_id=message_id)
        .order_by("-outer_attempt", "-inner_attempt")
        .first()
    )
    if attempt is None:
        raise ReplayRefused(
            f"No delivery in the log has message id {message_id!r}. A replay is driven from "
            f"the log, so a delivery that was never logged cannot be replayed."
        )

    endpoint = attempt.endpoint
    if endpoint is None:
        raise ReplayRefused(
            f"The endpoint delivery {message_id!r} was sent to has been deleted. Its log rows "
            f"are kept as evidence of where the request went, which is not the same as a "
            f"destination to send it to again."
        )

    if not endpoint.is_active:
        raise ReplayRefused(
            f"Endpoint {endpoint.name!r} is not active, so a replayed delivery would be "
            f"fired, claimed and then quietly dropped. Reactivate it first if that is what "
            f"you meant."
        )

    event_name = (
        EventRecord.objects.filter(pk=attempt.source_event_id)
        .values_list("name", flat=True)
        .first()
    )
    if event_name is None:
        raise ReplayRefused(
            f"Event {attempt.source_event_id} is no longer in the log, so delivery "
            f"{message_id!r} cannot be rendered again. Retention has outrun replay."
        )

    if registry.event_for_name(event_name) is None:
        raise ReplayRefused(
            f"Event {event_name!r} is no longer declared, so delivery {message_id!r} "
            f"cannot be replayed. Most often the event class was renamed; pin its old "
            f"name with @event(name=...)."
        )

    target = DeliveryTarget(
        endpoint_id=endpoint.pk,
        format_name=endpoint.format_name,
        format_version=endpoint.format_version,
        message_id=str(uuid.uuid4()),
    )
    token = replay_target.set((attempt.source_event_id, target))
    try:
        replay_events([attempt.source_event_id], receiver_keys=[RECEIVER_KEY])
    finally:
        replay_target.reset(token)
    return target.message_id
