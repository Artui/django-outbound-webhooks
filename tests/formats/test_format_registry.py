"""What formats exist, and which version an endpoint may pin."""

from __future__ import annotations

from typing import Any

import pytest

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats
from django_outbound_webhooks.types.format_id import FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody


class _Stub(BodyFormat):
    def __init__(self, name: str, version: int) -> None:
        self.name = name
        self.version = version

    def render(
        self, *, message_id: str, event_name: str, occurred_at: str, payload: dict[str, Any]
    ) -> RenderedBody:
        return RenderedBody(body=b"{}", content_type="application/json")


@pytest.fixture
def registry() -> FormatRegistry:
    return FormatRegistry()


def test_a_registered_format_is_retrievable_by_its_identity(registry: FormatRegistry) -> None:
    stub = _Stub("envelope", 1)
    registry.register(stub)
    assert registry.get(FormatId(name="envelope", version=1)) is stub


def test_registering_the_same_object_twice_is_fine(registry: FormatRegistry) -> None:
    # This is what a double import looks like, and refusing it would make the
    # package fail on an ordinary re-entrant load rather than on a real mistake.
    stub = _Stub("envelope", 1)
    registry.register(stub)
    registry.register(stub)
    assert registry.published() == [FormatId(name="envelope", version=1)]


def test_replacing_a_published_version_is_refused(registry: FormatRegistry) -> None:
    # The whole point of pinning. Silently swapping the renderer behind
    # envelope@1 changes what an integrated consumer receives, under a
    # signature that still verifies.
    registry.register(_Stub("envelope", 1))
    with pytest.raises(ValueError, match="already published"):
        registry.register(_Stub("envelope", 1))


def test_a_new_version_of_a_published_family_is_allowed(registry: FormatRegistry) -> None:
    registry.register(_Stub("envelope", 1))
    registry.register(_Stub("envelope", 2))
    assert registry.published() == [
        FormatId(name="envelope", version=1),
        FormatId(name="envelope", version=2),
    ]


def test_an_unpublished_identity_fails_closed_and_names_what_exists(
    registry: FormatRegistry,
) -> None:
    # Never a fallback to the current version: that would deliver a shape the
    # consumer never integrated against, which is what pinning prevents.
    registry.register(_Stub("envelope", 1))
    with pytest.raises(LookupError, match=r"envelope@2.*Published: envelope@1"):
        registry.get(FormatId(name="envelope", version=2))


def test_an_empty_registry_says_so_rather_than_listing_nothing(registry: FormatRegistry) -> None:
    with pytest.raises(LookupError, match="Published: nothing"):
        registry.get(FormatId(name="envelope", version=1))


def test_latest_is_what_a_registration_without_a_version_pins_to(
    registry: FormatRegistry,
) -> None:
    registry.register(_Stub("envelope", 1))
    registry.register(_Stub("envelope", 3))
    registry.register(_Stub("envelope", 2))
    registry.register(_Stub("cloudevents", 9))
    assert registry.latest("envelope") == FormatId(name="envelope", version=3)


def test_latest_of_an_unknown_family_names_the_families_that_exist(
    registry: FormatRegistry,
) -> None:
    registry.register(_Stub("envelope", 1))
    with pytest.raises(LookupError, match=r"'cloudevents'.*Families: envelope"):
        registry.latest("cloudevents")


def test_latest_on_an_empty_registry_says_none(registry: FormatRegistry) -> None:
    with pytest.raises(LookupError, match="Families: none"):
        registry.latest("envelope")


def test_published_is_ordered_by_family_then_version(registry: FormatRegistry) -> None:
    # An operator reads this to decide whether an old version can be retired.
    # An arbitrary order makes two runs of one census disagree.
    registry.register(_Stub("envelope", 2))
    registry.register(_Stub("cloudevents", 1))
    registry.register(_Stub("envelope", 1))
    assert [str(known) for known in registry.published()] == [
        "cloudevents@1",
        "envelope@1",
        "envelope@2",
    ]


def test_clear_empties_it(registry: FormatRegistry) -> None:
    registry.register(_Stub("envelope", 1))
    registry.clear()
    assert registry.published() == []


def test_the_app_publishes_the_built_in_envelope() -> None:
    # The process-wide registry, populated by WebhooksConfig.ready(). If the
    # app config stopped registering, every delivery would fail closed rather
    # than silently pick a format, and this is what says so.
    assert FormatId(name="envelope", version=1) in formats.published()
