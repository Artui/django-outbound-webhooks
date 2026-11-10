from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from django_outbound_webhooks.types.rendered_body import RenderedBody


@runtime_checkable
class BodyFormat(Protocol):
    """One frozen, published rendering of an event into a request body."""

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
        """Produce the bytes for one delivery."""
