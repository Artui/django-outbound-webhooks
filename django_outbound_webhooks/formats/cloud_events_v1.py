from __future__ import annotations

import json
from typing import Any

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.types.rendered_body import RenderedBody

#: The CloudEvents specification version these bodies declare, which is a
#: property of the wire shape rather than of this class. ``version = 1`` below
#: is *this package's* count of how many times the shape has been published;
#: the two numbers are unrelated and both have to be on the wire, because a
#: consumer reads ``specversion`` to parse the document and an endpoint pins
#: ours to say which rendering it integrated against.
SPEC_VERSION = "1.0"


class CloudEventsV1(BodyFormat):
    """One event rendered as a structured-mode CloudEvent."""

    name = "cloudevents"
    version = 1

    def __init__(self, *, source: str) -> None:
        """Publish this format for one producer."""
        if not source.strip():
            raise ValueError(
                "A CloudEvents source cannot be empty: it is what tells a consumer which "
                "system produced the event, and the specification requires it. Use the URI "
                "of the producing service, or a URN naming it."
            )
        self.source = source

    def render(
        self,
        *,
        message_id: str,
        event_name: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> RenderedBody:
        document = {
            "specversion": SPEC_VERSION,
            "id": message_id,
            "source": self.source,
            "type": event_name,
            "time": occurred_at,
            # Describes ``data``, not the document.
            "datacontenttype": "application/json",
            "data": payload,
        }
        body = json.dumps(
            document, separators=(",", ":"), sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        return RenderedBody(body=body, content_type="application/cloudevents+json; charset=UTF-8")
