"""What formats exist, and which version an endpoint may pin."""

from __future__ import annotations

from typing import Any

import pytest

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats
from django_outbound_webhooks.types.format_id import FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody


class _Stub:
    """A conforming format that inherits nothing.

    Deliberately not a subclass of ``BodyFormat``. The protocol is structural, so
    an operator's own format never has to import anything from this package, and
    a stub that inherited would be testing a coupling the design does not have.
    """

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


def test_an_object_inheriting_nothing_is_accepted(registry: FormatRegistry) -> None:
    # The point of the protocol. _Stub imports RenderedBody because it returns
    # one, and nothing else from this package.
    assert isinstance(_Stub("envelope", 1), BodyFormat)
    registry.register(_Stub("envelope", 1))


def test_inheriting_the_protocol_still_refuses_a_missing_render() -> None:
    # A protocol member with a bare `...` body is not abstract, so without the
    # @abstractmethod decorator this class would instantiate happily and fail at
    # delivery time. Anyone who does choose to inherit gets the refusal an
    # abstract base class would have given them.
    class Forgot(BodyFormat):
        name = "forgot"
        version = 1

    # Matched loosely on purpose. CPython words this differently across the
    # supported range -- "with abstract method render" before 3.12, "without an
    # implementation for abstract method 'render'" from 3.12 -- so pinning the
    # phrasing makes the test an assertion about the interpreter's wording
    # rather than about this package. What matters is that it refuses, and that
    # it names the member.
    with pytest.raises(TypeError, match=r"abstract method '?render'?"):
        Forgot()


def _renderer(self, *, message_id: str, event_name: str, occurred_at: str, payload: dict) -> Any:
    return RenderedBody(body=b"{}", content_type="application/json")


#: One object per missing attribute, built rather than mutated. Deleting an
#: attribute off a shared class leaks into every later test in the file, and the
#: restore is a second thing to get wrong.
_INCOMPLETE = {
    "name": type("NoName", (), {"version": 1, "render": _renderer}),
    "version": type("NoVersion", (), {"name": "x", "render": _renderer}),
    "render": type("NoRender", (), {"name": "x", "version": 1}),
}


@pytest.mark.parametrize("attribute", list(_INCOMPLETE))
def test_registration_refuses_an_object_missing_a_required_attribute(
    registry: FormatRegistry, attribute: str
) -> None:
    with pytest.raises(TypeError, match=f"no {attribute!r}"):
        registry.register(_INCOMPLETE[attribute]())


def test_registration_refuses_a_render_that_is_not_callable(registry: FormatRegistry) -> None:
    stub = _Stub("envelope", 1)
    stub.render = "not a callable"
    with pytest.raises(TypeError, match="not callable"):
        registry.register(stub)


def test_registration_refuses_a_render_with_the_wrong_keywords(
    registry: FormatRegistry,
) -> None:
    # The check that neither the protocol nor isinstance can make. This object
    # satisfies isinstance(x, BodyFormat) -- every attribute is present -- and
    # would raise TypeError at delivery time, hours later, in another process.
    class WrongKeywords:
        name = "wrong"
        version = 1

        def render(self, *, message_id: str, payload: dict[str, Any]) -> RenderedBody:
            return RenderedBody(body=b"{}", content_type="application/json")

    assert isinstance(WrongKeywords(), BodyFormat), "isinstance sees only that render exists"
    with pytest.raises(TypeError, match=r"'event_name', 'occurred_at'"):
        registry.register(WrongKeywords())


def test_a_render_taking_kwargs_is_accepted(registry: FormatRegistry) -> None:
    # Forwarding wrappers are legitimate and cannot name the keywords, so **kwargs
    # satisfies the check rather than failing it.
    class Forwarding:
        name = "forwarding"
        version = 1

        def render(self, **kwargs: Any) -> RenderedBody:
            return RenderedBody(body=b"{}", content_type="application/json")

    registry.register(Forwarding())
    assert registry.published() == [FormatId(name="forwarding", version=1)]


def test_positional_only_parameters_do_not_count_as_keywords(
    registry: FormatRegistry,
) -> None:
    # A parameter named message_id that cannot be passed by name is not a
    # parameter a delivery can fill, and the name alone would hide that.
    class PositionalOnly:
        name = "positional"
        version = 1

        def render(
            self, message_id: str, event_name: str, occurred_at: str, payload: dict[str, Any], /
        ) -> RenderedBody:
            return RenderedBody(body=b"{}", content_type="application/json")

    with pytest.raises(TypeError, match="does not accept"):
        registry.register(PositionalOnly())
