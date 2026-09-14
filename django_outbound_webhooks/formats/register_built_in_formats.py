"""Publish the formats this package ships."""

from __future__ import annotations

from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry
from django_outbound_webhooks.settings import setting


def register_built_in_formats(registry: FormatRegistry) -> None:
    """Publish the built-ins into one registry, through the operator's own door.

    Called from ``AppConfig.ready()`` with the process-wide registry. It takes
    the registry as an argument rather than reaching for that singleton so that
    what gets published for a given configuration can be asserted against a
    fresh one -- which matters here because publishing is conditional, and a
    condition tested by re-running ``ready()`` would also re-register the
    receivers and leave them behind for whatever ran next.

    ``envelope`` is unconditional. ``cloudevents`` is published only when
    ``CLOUDEVENTS_SOURCE`` says which system produced the events, because the
    specification requires a non-empty source and there is nothing to invent one
    from that would mean anything to a consumer -- and an invented one would be
    signed into every body. An unpublished family cannot be pinned, so the
    refusal lands at registration, naming what does exist.
    """
    registry.register(EnvelopeV1())

    source = setting("CLOUDEVENTS_SOURCE")
    if source is not None:
        registry.register(CloudEventsV1(source=source))
