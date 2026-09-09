"""What every body format has to provide."""

from __future__ import annotations

import abc
from typing import Any

from django_outbound_webhooks.types.rendered_body import RenderedBody


class BodyFormat(abc.ABC):
    """One frozen, published rendering of an event into a request body.

    An instance is one *version*. A format is not edited once an endpoint pins
    it: changing what version 1 renders changes what an already-integrated
    consumer receives, under a signature that still verifies, with nothing
    anywhere reporting the change. A change is a new version, and the golden
    fixtures in the test suite are what make that a gate rather than a note.

    ``render`` takes the message id because the id belongs in the body of most
    envelope shapes as well as in the signature, and a format that had to
    invent one would produce a different body on every attempt of the same
    delivery.
    """

    #: The family this version belongs to. Set on the subclass.
    name: str
    #: Which published version of that family this class is. Set on the subclass.
    version: int

    @abc.abstractmethod
    def render(
        self,
        *,
        message_id: str,
        event_name: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> RenderedBody:
        """Produce the bytes for one delivery.

        ``occurred_at`` arrives already formatted rather than as a datetime: it
        is read off the stored event row, and a format that re-serialised it
        would be free to disagree with the row it came from.
        """
