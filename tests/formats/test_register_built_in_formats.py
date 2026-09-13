"""Which built-in formats a given configuration publishes."""

from __future__ import annotations

from django.test import override_settings

from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry
from django_outbound_webhooks.formats.register_built_in_formats import register_built_in_formats
from django_outbound_webhooks.types.format_id import FormatId


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={})
def test_without_a_source_only_the_envelope_is_published() -> None:
    # The default, and the reason the function takes a registry: this state
    # cannot be reached by re-running ready() without also re-registering the
    # receivers into the process everything else in the suite shares.
    registry = FormatRegistry()
    register_built_in_formats(registry)
    assert [str(identity) for identity in registry.published()] == ["envelope@1"]


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"CLOUDEVENTS_SOURCE": "urn:acme:shop"})
def test_a_configured_source_publishes_cloudevents_with_it() -> None:
    registry = FormatRegistry()
    register_built_in_formats(registry)
    assert [str(identity) for identity in registry.published()] == [
        "cloudevents@1",
        "envelope@1",
    ]
    published = registry.get(FormatId(name="cloudevents", version=1))
    assert isinstance(published, CloudEventsV1)
    # The configured value reaches the wire, rather than merely deciding
    # whether anything was registered.
    assert published.source == "urn:acme:shop"


def test_the_process_registry_has_both_because_the_suite_configures_a_source() -> None:
    # Guards the wiring itself: the function is only correct if AppConfig.ready()
    # actually calls it, and every other test here builds its own registry.
    from django_outbound_webhooks.formats.format_registry import formats

    assert {identity.name for identity in formats.published()} >= {"envelope", "cloudevents"}
