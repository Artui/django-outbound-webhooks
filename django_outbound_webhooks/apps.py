"""The Django app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    """Publishes the built-in body formats once the app registry is ready.

    The built-ins go through the same ``formats.register(...)`` call an operator
    uses for their own, rather than being registered at module import. Two
    reasons, and the second is the one that matters: there is then one way to
    publish a format rather than a special case for ours, and an operator
    replacing or extending the set does it at a moment when the app registry is
    loaded and models can be imported.
    """

    name = "django_outbound_webhooks"
    verbose_name = "Outbound webhooks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Function-local by necessity, not by preference. Django imports an
        # app's AppConfig before the app registry is populated, so a
        # module-level import here would run too early for anything that
        # touches models -- which the formats do not today and an operator's
        # own format very well might.
        from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
        from django_outbound_webhooks.formats.format_registry import formats

        formats.register(EnvelopeV1())
