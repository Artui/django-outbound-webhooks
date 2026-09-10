"""Render, sign and send one endpoint's copy of an event."""

from __future__ import annotations

from django_domain_events import DeliveryContext

from django_outbound_webhooks.delivery.send_webhook import send_webhook
from django_outbound_webhooks.delivery.webhook_client import webhook_client
from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.signing_secrets import signing_secrets
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

    lease_seconds = setting("DELIVERY_LEASE_SECONDS")
    with webhook_client() as client:
        verdict = send_webhook(
            client=client,
            url=endpoint.url,
            secrets=signing_secrets(endpoint),
            message_id=due.message_id,
            body=body,
            lease_seconds=lease_seconds,
        )

    if verdict is not DeliveryVerdict.SUCCEEDED:
        raise DeliveryFailed(
            f"Delivery {due.message_id} to endpoint {due.endpoint_id} came back "
            f"{verdict.value} on attempt {context.attempt}."
        )
