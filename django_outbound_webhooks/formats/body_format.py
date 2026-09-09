"""What every body format has to provide."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from django_outbound_webhooks.types.rendered_body import RenderedBody


@runtime_checkable
class BodyFormat(Protocol):
    """One frozen, published rendering of an event into a request body.

    An instance is one *version*. A format is not edited once an endpoint pins
    it: changing what version 1 renders changes what an already-integrated
    consumer receives, under a signature that still verifies, with nothing
    anywhere reporting the change. A change is a new version, and the golden
    fixtures in the test suite are what make that a gate rather than a note.

    A ``Protocol`` rather than an abstract base class, because this is a library
    boundary. An operator's own format is theirs -- a dataclass, an instance of
    something that already exists in their project, an object built by a factory
    -- and requiring it to inherit from a class in this package buys nothing and
    costs them an import in a module that otherwise has no reason to know we
    exist.

    ``render`` is still ``@abstractmethod``, which is not redundant. A protocol
    member with a bare ``...`` body is *not* abstract, so a subclass that
    forgets to implement it instantiates happily and fails at delivery time
    instead. With the decorator, anyone who does choose to inherit -- and it is
    a reasonable thing to want, for the docstring and the checker -- gets the
    same refusal an abstract base class would have given them, while structural
    conformance still needs no inheritance at all.

    Neither of those is what protects the registry, however. ``isinstance`` against a
    runtime-checkable protocol tests only that the attributes *exist*, not what
    shape they have, so a ``render`` taking the wrong keywords passes it. The
    check that matters lives in ``FormatRegistry.register``.
    """

    #: The family this version belongs to.
    name: str
    #: Which published version of that family this object is.
    version: int

    @abstractmethod
    def render(
        self,
        *,
        message_id: str,
        event_name: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> RenderedBody:
        """Produce the bytes for one delivery.

        ``message_id`` is passed in rather than generated because it belongs in
        the body of most envelope shapes as well as in the signature, and a
        format that invented one would render different bytes on every attempt
        of the same delivery.

        ``occurred_at`` arrives already formatted rather than as a datetime: it
        is read off the stored event row, and a format that re-serialised it
        would be free to disagree with the row it came from.
        """
