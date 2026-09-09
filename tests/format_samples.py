"""The inputs every published format is rendered against for its golden fixture.

Shared by the fixture generator in ``scripts/`` and by the test that verifies
the checked-in bytes, so the two cannot drift into rendering different inputs
and agreeing anyway.
"""

from __future__ import annotations

from typing import Any

#: One case per published format identity. The payload is deliberately awkward:
#: a non-ASCII string, a key that sorts after another added later, a nested
#: object and a null, so a change in encoding, escaping or key order shows up as
#: a byte difference rather than passing on a payload too simple to disagree.
CASES: dict[str, dict[str, Any]] = {
    "envelope-v1.json": {
        "message_id": "msg_2b7f1c9e4a3d4f8e",
        "event_name": "shop.OrderPlaced",
        "occurred_at": "2026-09-09T12:34:56.789012+00:00",
        "payload": {
            "order_id": 42,
            "customer": {"name": "Ana Lindström", "vip": True},
            "coupon": None,
            "total_cents": 19900,
            "currency": "SEK",
        },
    }
}


def rendered(name: str) -> bytes:
    """Render one case through the registry, exactly as a delivery would."""
    from django_outbound_webhooks.formats.format_registry import formats
    from django_outbound_webhooks.types.format_id import FormatId

    family, _, version = name.removesuffix(".json").rpartition("-v")
    body_format = formats.get(FormatId(name=family, version=int(version)))
    return body_format.render(**CASES[name]).body
