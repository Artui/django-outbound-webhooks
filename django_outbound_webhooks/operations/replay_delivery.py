"""Send one logged delivery again."""

from __future__ import annotations

import uuid

from django_domain_events import registry, replay_events

from django_outbound_webhooks.delivery.deliver_due import RECEIVER_KEY
from django_outbound_webhooks.delivery.replay_target import replay_target
from django_outbound_webhooks.types.delivery_target import DeliveryTarget


class ReplayRefused(Exception):
    """A delivery cannot be replayed, and the message says what is missing.

    One exception for all five refusals rather than five, because the caller is
    an operator tool -- a management command, an admin action, a support script
    -- and every one of them wants to show the reason rather than branch on it.
    """


def replay_delivery(*, message_id: str) -> str:
    """Fire a fresh delivery of a logged one, and return its new ``webhook-id``.

    A replay is a **new delivery**, not a re-run of an old one, and every
    decision here follows from that.

    It gets a **new message id**. A receiver deduplicates on ``webhook-id``, so
    replaying under the original id is asking a well-behaved consumer to discard
    exactly the delivery somebody asked for. A first delivery's id is random
    rather than derived for this reason.

    It re-reads the endpoint's **current** pinned format rather than the one in
    the log. The pin is the consumer's integration contract as it stands today:
    if it moved, the old shape is the one they can no longer parse. This is the
    same rule a first delivery follows -- read the pin when the delivery is
    minted, freeze it for that delivery's retries.

    It goes through the substrate's own ``replay_events`` like any other
    delivery, so it gets its own delivery row, attempt budget, backoff,
    dead-lettering and log rows. That operation asks the delivery receiver for
    its targets again, and would be told every endpoint subscribed now - which
    is what replaying a whole event means. ``replay_target`` narrows the
    question to this one delivery for the length of the call. Nothing here
    posts anything: this returns as soon as the row is written, and the relay
    does the work.
    """
    # Both imported here rather than at module scope: Django imports an app's
    # package before the app registry is ready, and this package's __init__
    # re-exports this function, so a model imported up there would raise
    # AppRegistryNotReady.
    from django_domain_events.models.event_record import EventRecord

    from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt

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
        # The substrate replays only events it can rebuild, and skips the rest
        # without saying so. Refused here instead, so the operator is not told a
        # replay happened when no row was written.
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
        # Reset in a finally, and tied to one event id besides. A value that
        # outlived this call would narrow the next replay in this context too.
        replay_target.reset(token)
    return target.message_id
