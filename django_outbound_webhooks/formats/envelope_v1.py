"""The default body format, version 1."""

from __future__ import annotations

import json
from typing import Any

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.types.rendered_body import RenderedBody


class EnvelopeV1(BodyFormat):
    """A typed envelope around the event's own payload.

    The shape most webhook consumers already expect: an id to deduplicate on, a
    type to branch on, a timestamp, and the payload nested under ``data`` rather
    than spread across the top level. Nesting is what lets a later version add
    envelope fields without any chance of colliding with a payload key.

    Every serialisation knob is pinned -- ``separators``, ``sort_keys`` and
    ``ensure_ascii`` -- because the output is signed and its hash is recorded.
    Left to their defaults, a json module that changed its spacing or its escaping
    would change every signature this format produces, and the change would look
    like a signing bug rather than a serialisation one. ``ensure_ascii`` is the
    easiest of the three to leave off, and the only one whose effect is invisible
    until a payload carries a non-ASCII character.
    """

    name = "envelope"
    version = 1

    def render(
        self,
        *,
        message_id: str,
        event_name: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> RenderedBody:
        document = {
            "id": message_id,
            "type": event_name,
            "timestamp": occurred_at,
            "data": payload,
        }
        body = json.dumps(
            document, separators=(",", ":"), sort_keys=True, ensure_ascii=True
        ).encode("utf-8")
        return RenderedBody(body=body, content_type="application/json")
