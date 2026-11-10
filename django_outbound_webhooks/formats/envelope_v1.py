from __future__ import annotations

import json
from typing import Any

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.types.rendered_body import RenderedBody


class EnvelopeV1(BodyFormat):
    """A typed envelope around the event's own payload."""

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
