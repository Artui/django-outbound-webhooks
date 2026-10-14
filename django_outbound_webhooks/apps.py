"""The Django app configuration."""

from __future__ import annotations

from django.apps import AppConfig
from django.core.checks import register

from django_outbound_webhooks.checks import check_default_format_is_published


class WebhooksConfig(AppConfig):
    """Publishes the built-in formats and declares the delivery receiver, once apps are ready.

    Everything happens here rather than at module import for one reason that
    applies to all of it: this is the first moment when settings are readable and
    models are importable, and both the format registry and the receiver
    registration need one or the other.
    """

    name = "django_outbound_webhooks"
    verbose_name = "Outbound webhooks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # The receiver-side imports below stay inside ready(). deliver_due,
        # delivery_targets and record_failed_attempts reach the models or declare
        # an @event, and importing any of them while the app registry is still
        # populating raises AppRegistryNotReady. Django imports this module before
        # that point, so moving those three to module scope fails the same way.
        # The other names here import without the registry; they stay with the
        # wiring they serve.
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

        # Registered here because nothing else imports checks.py at runtime: a
        # decorator on the function would register it only where something had
        # imported the module, which no deployment does.
        register(check_default_format_is_published)

        # The lease is declared here and spent inside send_webhook, from the same
        # setting. Two numbers would be two ways for the receiver's lease and the
        # retry's deadline to disagree, and the cost of disagreeing is a delivery
        # sent by a worker that no longer owns the row.
        #
        # One receiver for every event. A wildcard is matched when an event is
        # fired rather than when it is declared, so an event declared by an app
        # that loads after this one reaches endpoints like any other, and the
        # order of INSTALLED_APPS does not matter. targets= is what keeps it
        # from owing every event in the system: an event no endpoint subscribes
        # to writes no delivery row at all.
        receiver(
            AnyEvent,
            key=RECEIVER_KEY,
            takes_context=True,
            lease_seconds=setting("DELIVERY_LEASE_SECONDS"),
            # The other half of the delivery log. A receiver's writes are
            # discarded when it raises, so the attempts worth recording are the
            # ones it cannot record; this runs outside that rollback.
            on_failure=record_failed_attempts,
            # One delivery row per endpoint owed the event, each with its own
            # attempts, backoff and dead-letter. Runs at fire time, inside the
            # transaction that fired the event.
            targets=delivery_targets,
        )(deliver_due)
