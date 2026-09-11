"""The Django app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    """Publishes the built-in formats and wires the fan-out, once apps are ready.

    Everything happens here rather than at module import for one reason that
    applies to all of it: this is the first moment when settings are readable and
    models are importable, and both the format registry and the receiver
    registration need one or the other.
    """

    name = "django_outbound_webhooks"
    verbose_name = "Outbound webhooks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Function-local by necessity, not preference. Django imports an app's
        # AppConfig before the app registry is populated, so a module-level
        # import here would run too early for anything touching models -- which
        # the fan-out registration does transitively.
        from django_domain_events import receiver

        from django_outbound_webhooks.delivery.deliver_due import deliver_due
        from django_outbound_webhooks.delivery.record_failed_attempts import (
            record_failed_attempts,
        )
        from django_outbound_webhooks.delivery.register_fan_out import register_fan_out
        from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
        from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
        from django_outbound_webhooks.formats.format_registry import formats
        from django_outbound_webhooks.settings import setting

        formats.register(EnvelopeV1())

        # The lease is declared here and spent inside send_webhook, from the same
        # setting. Two numbers would be two ways for the receiver's lease and the
        # retry's deadline to disagree, and the cost of disagreeing is a delivery
        # sent by a worker that no longer owns the row.
        receiver(
            WebhookDeliveryDue,
            key="django_outbound_webhooks.deliver",
            takes_context=True,
            lease_seconds=setting("DELIVERY_LEASE_SECONDS"),
            # The other half of the delivery log. A receiver's writes are
            # discarded when it raises, so the attempts worth recording are the
            # ones it cannot record; this runs outside that rollback.
            on_failure=record_failed_attempts,
        )(deliver_due)

        register_fan_out()
