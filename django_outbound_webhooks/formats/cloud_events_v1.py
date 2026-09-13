"""The CloudEvents body format, version 1."""

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
    """One event rendered as a structured-mode CloudEvent.

    The second published format, and the one that says whether the seam works.
    A first format proves nothing: it can be whatever the renderer happened to
    produce. This one is a shape somebody else specified, chosen for that
    reason -- if adding it had needed a new argument on ``render`` or a new
    column on the endpoint, the seam would have been wrong and this is where
    that would have shown.

    It needed neither. What it does need is a ``source``, and the answer to
    where that comes from is the interesting part: it identifies the *producer*,
    so it is the same value for every endpoint in a deployment and belongs to
    the operator rather than the customer. That makes it constructor state on
    the format instance -- which the protocol already allows, because a format
    is an object rather than a class of static methods. A per-endpoint source
    would have been a column, and a column would have been the seam failing.

    Differences from :class:`~django_outbound_webhooks.formats.envelope_v1.EnvelopeV1`
    that are deliberate rather than incidental:

    * The content type is ``application/cloudevents+json``, not
      ``application/json``. Structured mode says the media type is how a
      consumer knows the document is an event rather than a payload, and this
      is the first thing here to exercise the fact that the content type
      travels with the bytes instead of being fixed by the sender.
    * ``ensure_ascii`` is **off**, where the envelope has it on. The media type
      declares ``charset=UTF-8``, and the specification's JSON encoding is
      UTF-8, so escaping every non-ASCII character to ``\\uXXXX`` would be
      valid, larger and pointless. It is still pinned rather than left to the
      default, for the reason the envelope pins it: the bytes are signed and
      their hash is recorded, so a json module that changed its escaping would
      change every signature and it would read as a signing bug.

    The attributes are exactly the ones this package can honestly fill.
    ``subject`` and ``dataschema`` are omitted rather than guessed: both are
    claims about the producer's domain, and a wrong one is worse than an absent
    one because it is optional and a consumer that sees it will use it.
    """

    name = "cloudevents"
    version = 1

    def __init__(self, *, source: str) -> None:
        """Publish this format for one producer.

        ``source`` is required and validated here rather than at render time,
        on the same principle as the registry's conformance check: a format is
        constructed once at startup and called hours later in another process,
        so a fault found now is a traceback an operator reads, and the same
        fault found then is a dead-lettered delivery.
        """
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
            # Describes ``data``, not the document. Omitting it would also be
            # conformant -- the JSON format assumes JSON data -- but a consumer
            # routing on it should not have to know that the absence means the
            # same thing as the value.
            "datacontenttype": "application/json",
            # Nested, exactly as the envelope nests it, and for the same reason
            # one level up: a payload key called `type` or `id` would otherwise
            # overwrite the attribute a consumer branches on.
            "data": payload,
        }
        body = json.dumps(
            document, separators=(",", ":"), sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        return RenderedBody(body=body, content_type="application/cloudevents+json; charset=UTF-8")
