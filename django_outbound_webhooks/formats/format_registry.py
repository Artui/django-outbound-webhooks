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
    """Refuse an object that cannot serve as a body format, at registration."""
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
    """The published body formats, keyed by name and version."""

    def __init__(self) -> None:
        self._formats: dict[FormatId, BodyFormat] = {}

    def register(self, body_format: BodyFormat) -> None:
        """Publish one version of one format."""
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
        """The renderer for one pinned identity, or a refusal naming what exists."""
        body_format = self._formats.get(identity)
        if body_format is None:
            published = ", ".join(str(known) for known in self.published()) or "nothing"
            raise LookupError(f"No body format is published as {identity}. Published: {published}.")
        return body_format

    def latest(self, name: str) -> FormatId:
        """The newest published version of one format family."""
        versions = [known for known in self._formats if known.name == name]
        if not versions:
            families = ", ".join(sorted({known.name for known in self._formats})) or "none"
            raise LookupError(f"No body format is published under {name!r}. Families: {families}.")
        return max(versions, key=lambda known: known.version)

    def published(self) -> list[FormatId]:
        """Every published identity, oldest family and version first."""
        return sorted(self._formats, key=lambda known: (known.name, known.version))

    def clear(self) -> None:
        """Empty the registry. For tests; nothing in the package calls it."""
        self._formats.clear()


#: The process-wide registry. Populated by ``WebhooksConfig.ready()``, which
#: registers this package's built-in formats through the same call an operator
#: uses for their own -- so there is one way to publish a format, not two.
formats = FormatRegistry()
