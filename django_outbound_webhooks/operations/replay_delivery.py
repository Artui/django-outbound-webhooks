"""Send one logged delivery again."""

from __future__ import annotations

import uuid

from django.db import transaction
from django_domain_events import fire


class ReplayRefused(Exception):
    """A delivery cannot be replayed, and the message says what is missing.

    One exception for all four refusals rather than four, because the caller is
    an operator tool -- a management command, an admin action, a support script
    -- and every one of them wants to show the reason rather than branch on it.
    """


def replay_delivery(*, message_id: str) -> str:
    """Fire a fresh delivery of a logged one, and return its new ``webhook-id``.

    A replay is a **new delivery**, not a re-run of an old one, and every
    decision here follows from that.

    It gets a **new message id**. A receiver deduplicates on ``webhook-id``, so
    replaying under the original id is asking a well-behaved consumer to discard
    exactly the delivery somebody asked for. The fan-out already mints ids
    rather than deriving them for this reason.

    It re-reads the endpoint's **current** pinned format rather than the one in
    the log. The pin is the consumer's integration contract as it stands today:
    if it moved, the old shape is the one they can no longer parse. This is the
    same rule the fan-out follows -- read the pin when the delivery is minted,
    freeze it for that delivery's retries.

    It goes through the substrate like any other delivery, so it gets its own
    delivery row, attempt budget, backoff, dead-lettering and log rows. Nothing
    here posts anything: this function returns as soon as the event is written,
    and the relay does the work.
    """
    # All three imported here rather than at module scope, for one reason that
    # covers both kinds: Django imports an app's package before the app registry
    # is ready, and this package's __init__ re-exports this function. A model
    # imported up there would raise AppRegistryNotReady -- and so would
    # WebhookDeliveryDue, because @event resolves an event's name through the
    # app registry too, which makes an event class exactly as unimportable as a
    # model at that moment.
    from django_domain_events.models.event_record import EventRecord

    from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
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

    if not EventRecord.objects.filter(pk=attempt.source_event_id).exists():
        raise ReplayRefused(
            f"Event {attempt.source_event_id} is no longer in the log, so delivery "
            f"{message_id!r} cannot be rendered again. Retention has outrun replay."
        )

    replayed_id = str(uuid.uuid4())
    with transaction.atomic():
        fire(
            WebhookDeliveryDue(
                endpoint_id=endpoint.pk,
                source_event_id=attempt.source_event_id,
                format_name=endpoint.format_name,
                format_version=endpoint.format_version,
                message_id=replayed_id,
            )
        )
    return replayed_id
