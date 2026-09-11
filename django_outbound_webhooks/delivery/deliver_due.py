"""Render, sign and send one endpoint's copy of an event."""

from __future__ import annotations

import hashlib

from django_domain_events import DeliveryContext

from django_outbound_webhooks.delivery.pending_attempts import PendingAttempts, pending_attempts
from django_outbound_webhooks.delivery.record_attempts import record_attempts
from django_outbound_webhooks.delivery.send_webhook import send_webhook
from django_outbound_webhooks.delivery.webhook_client import webhook_client
from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.signing_secrets import signing_secrets
from django_outbound_webhooks.types.attempt_outcome import AttemptOutcome
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.format_id import FormatId


class DeliveryFailed(Exception):
    """One delivery did not succeed, and the substrate should decide what next.

    Raised rather than returned because raising is the only thing the substrate
    reads. It cannot be told a failure is terminal, so a permanent verdict still
    burns the attempt budget before dead-lettering -- wasteful, correct in the
    end, and the first of the findings this package owes back.
    """


def deliver_due(due: WebhookDeliveryDue, context: DeliveryContext) -> None:
    """Deliver one copy, or raise so the substrate retries it.

    Imported inside the function for the reason the substrate documents: Django
    imports an app's package before the app registry is ready, and these are
    models.
    """
    from django_domain_events.models.event_record import EventRecord

    from django_outbound_webhooks.models.endpoint import Endpoint

    endpoint = Endpoint.objects.filter(pk=due.endpoint_id).first()
    if endpoint is None or not endpoint.is_active:
        # Deleted or switched off between the fan-out and now. Nothing is owed,
        # and returning quietly is what says so: raising would retry a delivery
        # whose destination the customer removed on purpose.
        return

    source = EventRecord.objects.filter(pk=due.source_event_id).first()
    if source is None:
        # Pruned out from under us. The bytes cannot be reconstructed, so this
        # can never succeed; it raises to be recorded rather than returning,
        # because a delivery that silently never happened is the failure mode
        # this package exists to avoid.
        raise DeliveryFailed(
            f"Event {due.source_event_id} is no longer in the log, so delivery "
            f"{due.message_id} can never be rendered. Retention is outrunning delivery."
        )

    body_format = formats.get(FormatId(name=due.format_name, version=due.format_version))
    body = body_format.render(
        message_id=due.message_id,
        event_name=source.name,
        occurred_at=source.occurred_at.isoformat(),
        payload=source.payload,
    )

    outcomes: list[AttemptOutcome] = []
    # Set before the first request, and never cleared here. The failure hook
    # runs after this function has already raised, so clearing on the way out
    # would empty it before its only reader looks.
    pending = PendingAttempts(
        due=due,
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
            message_id=due.message_id,
            body=body,
            lease_seconds=lease_seconds,
            history=outcomes,
        )

    if final.verdict is not DeliveryVerdict.SUCCEEDED:
        # The log is written by the failure hook instead, from outside the
        # transaction this raise is about to roll back.
        raise DeliveryFailed(
            f"Delivery {due.message_id} to endpoint {due.endpoint_id} came back "
            f"{final.verdict.value} on outer attempt {context.attempt} after "
            f"{len(outcomes)} request(s)."
        )

    # Read back through a local rather than the context variable: the variable's
    # type is optional and this one is not, and asserting it here would be
    # asserting something this function just did.
    record_attempts(pending)
    pending_attempts.set(None)
