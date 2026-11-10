from __future__ import annotations

from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry
from django_outbound_webhooks.settings import setting


def register_built_in_formats(registry: FormatRegistry) -> None:
    """Publish the built-ins into one registry, through the operator's own door."""
    registry.register(EnvelopeV1())

    source = setting("CLOUDEVENTS_SOURCE")
    if source is not None:
        registry.register(CloudEventsV1(source=source))
