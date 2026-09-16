"""What formats exist, and which version an endpoint may pin."""

from __future__ import annotations

import inspect

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.types.format_id import FormatId

#: The keywords a delivery calls ``render`` with. Checked at registration
#: because a format is registered once, at startup, and called hours later in
#: another process: a signature mismatch found then is a dead-lettered delivery
#: with a TypeError on it. The substrate makes the same trade for the same
#: reason -- its ``receiver`` decorator is overloaded so that declaring one
#: arity and writing another fails at the decorator rather than in the relay.
_RENDER_KEYWORDS = ("message_id", "event_name", "occurred_at", "payload")


def _require_conforming(body_format: BodyFormat) -> None:
    """Refuse an object that cannot serve as a body format, at registration.

    Neither of the type-level tools does this job. ``isinstance`` against a
    runtime-checkable protocol tests attribute *presence* only, so a ``render``
    with entirely the wrong keywords satisfies it; and a protocol demands no
    inheritance, so there is no constructor anywhere to enforce a shape. The
    checker catches this for code it can see, and an operator's format lives in
    a project it cannot.

    The parameter is annotated as the thing this function verifies, which reads
    as circular and is the usual arrangement: the annotation says what the
    caller believes it is passing, and the body is what establishes whether that
    was true.
    """
    for attribute in ("name", "version", "render"):
        if not hasattr(body_format, attribute):
            raise TypeError(
                f"{type(body_format).__name__} cannot be published as a body format: it has "
                f"no {attribute!r}. A format needs a name, a version and a render()."
            )

    render = body_format.render
    if not callable(render):
        raise TypeError(
            f"{type(body_format).__name__}.render is not callable, so nothing could render a "
            f"delivery with it."
        )

    parameters = inspect.signature(render).parameters
    if any(kind.kind is inspect.Parameter.VAR_KEYWORD for kind in parameters.values()):
        return

    accepted = {
        name
        for name, parameter in parameters.items()
        if parameter.kind
        in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    }
    missing = [keyword for keyword in _RENDER_KEYWORDS if keyword not in accepted]
    if missing:
        raise TypeError(
            f"{type(body_format).__name__}.render does not accept "
            f"{', '.join(repr(name) for name in missing)} as a keyword. A delivery calls it "
            f"with {', '.join(_RENDER_KEYWORDS)}, all by keyword."
        )


class FormatRegistry:
    """The published body formats, keyed by name and version.

    Operator-owned. A customer *selects* from what is registered here and can
    never add to it: a customer-supplied renderer is an injection surface, and
    it would sit directly against the boundary that decides whose payload
    reaches whose URL.
    """

    def __init__(self) -> None:
        self._formats: dict[FormatId, BodyFormat] = {}

    def register(self, body_format: BodyFormat) -> None:
        """Publish one version of one format.

        Registering the same identity twice with a *different* object is
        refused rather than tolerated. Once an endpoint pins ``envelope@1``,
        that identity names the bytes it integrated against, so silently
        replacing the renderer behind it would change what an existing consumer
        receives under a signature that still verifies. Re-registering the same
        object is fine and is what a double import looks like.
        """
        _require_conforming(body_format)
        identity = FormatId(name=body_format.name, version=body_format.version)
        existing = self._formats.get(identity)
        if existing is not None and existing is not body_format:
            raise ValueError(
                f"{identity} is already published by {type(existing).__name__} and cannot be "
                f"re-registered by {type(body_format).__name__}. An endpoint pins a version "
                f"because the bytes it renders are frozen; publish a new version instead."
            )
        self._formats[identity] = body_format

    def get(self, identity: FormatId) -> BodyFormat:
        """The renderer for one pinned identity, or a refusal naming what exists.

        Fails closed. An endpoint pinned to something unpublished must not fall
        back to a current version: that would deliver a shape the consumer never
        integrated against, which is the exact outcome pinning exists to
        prevent.
        """
        body_format = self._formats.get(identity)
        if body_format is None:
            published = ", ".join(str(known) for known in self.published()) or "nothing"
            raise LookupError(f"No body format is published as {identity}. Published: {published}.")
        return body_format

    def latest(self, name: str) -> FormatId:
        """The newest published version of one format family.

        This is what a registration with no stated version pins *to*, and the
        answer is recorded on the endpoint rather than re-derived, so the
        endpoint stops moving the moment it is created.
        """
        versions = [known for known in self._formats if known.name == name]
        if not versions:
            families = ", ".join(sorted({known.name for known in self._formats})) or "none"
            raise LookupError(f"No body format is published under {name!r}. Families: {families}.")
        return max(versions, key=lambda known: known.version)

    def published(self) -> list[FormatId]:
        """Every published identity, oldest family and version first.

        Sorted because this is what an operator reads when deciding whether a
        version can be retired, and an arbitrary order makes two runs of the
        same census disagree.
        """
        return sorted(self._formats, key=lambda known: (known.name, known.version))

    def clear(self) -> None:
        """Empty the registry. For tests; nothing in the package calls it."""
        self._formats.clear()


#: The process-wide registry. Populated by ``WebhooksConfig.ready()``, which
#: registers this package's built-in formats through the same call an operator
#: uses for their own -- so there is one way to publish a format, not two.
formats = FormatRegistry()
