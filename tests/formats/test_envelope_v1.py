"""The default body format, and the bytes it is frozen at."""

from __future__ import annotations

import json
from pathlib import Path

from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "formats"


def test_it_wraps_the_payload_under_data() -> None:
    rendered = EnvelopeV1().render(
        message_id="msg_1",
        event_name="shop.OrderPlaced",
        occurred_at="2026-09-09T00:00:00+00:00",
        payload={"order_id": 7},
    )
    document = json.loads(rendered.body)
    assert document == {
        "id": "msg_1",
        "type": "shop.OrderPlaced",
        "timestamp": "2026-09-09T00:00:00+00:00",
        "data": {"order_id": 7},
    }
    assert rendered.content_type == "application/json"


def test_a_payload_key_cannot_collide_with_an_envelope_field() -> None:
    # Nesting under `data` is what buys this. A flat shape would let a payload
    # field called `type` overwrite the event name a consumer branches on.
    rendered = EnvelopeV1().render(
        message_id="msg_1",
        event_name="shop.OrderPlaced",
        occurred_at="2026-09-09T00:00:00+00:00",
        payload={"id": "not-the-message-id", "type": "not-the-event-name"},
    )
    document = json.loads(rendered.body)
    assert document["id"] == "msg_1"
    assert document["type"] == "shop.OrderPlaced"
    assert document["data"] == {"id": "not-the-message-id", "type": "not-the-event-name"}


def test_the_bytes_are_deterministic() -> None:
    # The body is signed and its hash is recorded, so two renderings of one
    # delivery have to be byte-identical or a retry fails verification against
    # the id it reuses.
    kwargs = {
        "message_id": "msg_1",
        "event_name": "shop.OrderPlaced",
        "occurred_at": "2026-09-09T00:00:00+00:00",
    }
    first = EnvelopeV1().render(payload={"b": 1, "a": 2}, **kwargs).body
    second = EnvelopeV1().render(payload={"a": 2, "b": 1}, **kwargs).body
    assert first == second, "key insertion order must not reach the wire"


def test_it_still_renders_the_bytes_it_was_published_with() -> None:
    # The gate. Regenerate with `uv run scripts/generate-format-fixtures
    # tests/fixtures/formats`; if that changes a checked-in file, the edit is a
    # new version rather than a fix.
    from tests.format_samples import rendered

    expected = (FIXTURES / "envelope-v1.json").read_bytes()
    assert rendered("envelope-v1.json") == expected


def test_the_fixture_is_not_vacuous() -> None:
    # A golden test passes against an empty file if the renderer also returns
    # nothing, and it passes against any file if the sample payload has nothing
    # in it that could reorder or escape. Assert the fixture actually exercises
    # both.
    expected = (FIXTURES / "envelope-v1.json").read_bytes()
    assert b"\\u00f6" in expected, "the sample must carry a non-ASCII character"
    assert expected.index(b'"coupon"') < expected.index(b'"currency"'), "keys must be sorted"
