from __future__ import annotations

from django.apps import AppConfig
from django.core.checks import register

from django_outbound_webhooks.checks import check_default_format_is_published


class WebhooksConfig(AppConfig):
    """Publishes the built-in formats and declares the delivery receiver, once apps are ready."""

    name = "django_outbound_webhooks"
    verbose_name = "Outbound webhooks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # The receiver-side imports below stay inside ready().
        from django_domain_events import AnyEvent, receiver

        from django_outbound_webhooks.delivery.deliver_due import RECEIVER_KEY, deliver_due
        from django_outbound_webhooks.delivery.delivery_targets import delivery_targets
        from django_outbound_webhooks.delivery.record_failed_attempts import (
            record_failed_attempts,
        )
        from django_outbound_webhooks.formats.format_registry import formats
        from django_outbound_webhooks.formats.register_built_in_formats import (
            register_built_in_formats,
        )
        from django_outbound_webhooks.settings import setting

        register_built_in_formats(formats)

        register(check_default_format_is_published)

        receiver(
            AnyEvent,
            key=RECEIVER_KEY,
            takes_context=True,
            lease_seconds=setting("DELIVERY_LEASE_SECONDS"),
            on_failure=record_failed_attempts,
            targets=delivery_targets,
        )(deliver_due)
