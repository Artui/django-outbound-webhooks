from __future__ import annotations

import hashlib

from django_domain_events import DeliveryContext, RetryAfter
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.delivery.pending_attempts import PendingAttempts, pending_attempts
from django_outbound_webhooks.delivery.record_attempts import record_attempts
from django_outbound_webhooks.delivery.send_webhook import send_webhook
from django_outbound_webhooks.delivery.webhook_client import webhook_client
from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.note_successful_delivery import (
    note_successful_delivery,
)
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.signing_secrets import signing_secrets
from django_outbound_webhooks.types.attempt_outcome import AttemptOutcome
from django_outbound_webhooks.types.delivery_target import DeliveryTarget
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.format_id import FormatId

#: The key the delivery receiver is registered under. Every delivery row this
#: package owes names it, so it is stable across releases, and ``replay_delivery``
#: narrows a substrate replay to it.
RECEIVER_KEY = "django_outbound_webhooks.deliver"


class DeliveryFailed(Exception):
    """One delivery did not succeed, and the substrate should decide what next."""


def deliver_due(event: object, context: DeliveryContext) -> None:
    """Deliver one endpoint's copy of one event, or raise so the substrate retries it."""
    target = DeliveryTarget.decode(context.target)
    endpoint = Endpoint.objects.filter(pk=target.endpoint_id).first()
    if endpoint is None or not endpoint.is_active:
        return

    source = EventRecord.objects.get(pk=context.event_id)
    body_format = formats.get(FormatId(name=target.format_name, version=target.format_version))
    body = body_format.render(
        message_id=target.message_id,
        event_name=source.name,
        occurred_at=source.occurred_at.isoformat(),
        payload=source.payload,
    )

    outcomes: list[AttemptOutcome] = []
    pending = PendingAttempts(
        target=target,
        source_event_id=source.pk,
        url=endpoint.url,
        outer_attempt=context.attempt,
        request_body_sha256=hashlib.sha256(body.body).hexdigest(),
        request_body_bytes=len(body.body),
        outcomes=outcomes,
    )
    pending_attempts.set(pending)

    lease_seconds = setting("DELIVERY_LEASE_SECONDS")
    with webhook_client() as client:
        final = send_webhook(
            client=client,
            url=endpoint.url,
            secrets=signing_secrets(endpoint),
            message_id=target.message_id,
            body=body,
            lease_seconds=lease_seconds,
            history=outcomes,
        )

    if final.verdict is not DeliveryVerdict.SUCCEEDED:
        if final.retry_after_seconds is not None:
            raise RetryAfter(
                seconds=final.retry_after_seconds,
                reason=(
                    f"Delivery {target.message_id} to endpoint {target.endpoint_id} came back "
                    f"{final.status_code} on outer attempt {context.attempt}, asking to be "
                    f"retried in {final.retry_after_seconds:g}s."
                ),
            )
        raise DeliveryFailed(
            f"Delivery {target.message_id} to endpoint {target.endpoint_id} came back "
            f"{final.verdict.value} on outer attempt {context.attempt} after "
            f"{len(outcomes)} request(s)."
        )

    record_attempts(pending)
    note_successful_delivery(endpoint)
    pending_attempts.set(None)
