"""The CloudEvents format, and the seam claim it is here to test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "formats"

SOURCE = "https://shop.example/events"

CALL = {
    "message_id": "msg_1",
    "event_name": "shop.OrderPlaced",
    "occurred_at": "2026-09-09T00:00:00+00:00",
    "payload": {"order_id": 7},
}


def test_it_renders_a_structured_mode_cloudevent() -> None:
    rendered = CloudEventsV1(source=SOURCE).render(**CALL)
    assert json.loads(rendered.body) == {
        "specversion": "1.0",
        "id": "msg_1",
        "source": SOURCE,
        "type": "shop.OrderPlaced",
        "time": "2026-09-09T00:00:00+00:00",
        "datacontenttype": "application/json",
        "data": {"order_id": 7},
    }


def test_the_media_type_says_the_document_is_an_event() -> None:
    # Structured mode's whole mechanism: a consumer knows it received an event
    # rather than a payload because of the media type. Asserting the positive
    # alone would pass for a format that had copied the envelope's, so the
    # negative is what pins which one answered.
    rendered = CloudEventsV1(source=SOURCE).render(**CALL)
    assert rendered.content_type == "application/cloudevents+json; charset=UTF-8"
    assert rendered.content_type != EnvelopeV1().render(**CALL).content_type


def test_a_payload_key_cannot_overwrite_an_attribute() -> None:
    # Nesting under `data` buys this here exactly as it does in the envelope. A
    # flat document would let a payload field called `source` replace the
    # producer identity a consumer routes on.
    rendered = CloudEventsV1(source=SOURCE).render(
        message_id="msg_1",
        event_name="shop.OrderPlaced",
        occurred_at="2026-09-09T00:00:00+00:00",
        payload={"id": "not-the-message-id", "source": "not-the-producer", "specversion": "9.9"},
    )
    document = json.loads(rendered.body)
    assert document["id"] == "msg_1"
    assert document["source"] == SOURCE
    assert document["specversion"] == "1.0"
    assert document["data"]["source"] == "not-the-producer"


def test_the_bytes_are_deterministic() -> None:
    # Signed, and the hash recorded, so two renderings of one delivery have to
    # be byte-identical or a retry fails verification against the id it reuses.
    kwargs = {k: v for k, v in CALL.items() if k != "payload"}
    body_format = CloudEventsV1(source=SOURCE)
    first = body_format.render(payload={"b": 1, "a": 2}, **kwargs).body
    second = body_format.render(payload={"a": 2, "b": 1}, **kwargs).body
    assert first == second, "key insertion order must not reach the wire"


def test_non_ascii_travels_as_utf8_rather_than_escaped() -> None:
    # The one place these two formats encode differently, and it is deliberate:
    # the media type declares charset=UTF-8. The negative assertion is the half
    # that matters -- without it this passes for a renderer that escaped.
    body = (
        CloudEventsV1(source=SOURCE)
        .render(
            message_id="msg_1",
            event_name="shop.OrderPlaced",
            occurred_at="2026-09-09T00:00:00+00:00",
            payload={"name": "Ana Lindström"},
        )
        .body
    )
    assert "Lindström".encode() in body
    assert b"\\u00f6" not in body
    assert json.loads(body)["data"]["name"] == "Ana Lindström"


@pytest.mark.parametrize("source", ["", "   "])
def test_a_source_that_names_nothing_is_refused_at_construction(source: str) -> None:
    # At construction rather than at render, for the reason the registry checks
    # conformance there: a format is built once at startup and called hours
    # later in another process, where the same fault is a dead-lettered
    # delivery instead of a traceback someone is reading.
    with pytest.raises(ValueError, match="cannot be empty"):
        CloudEventsV1(source=source)


def test_it_needs_nothing_the_first_format_did_not() -> None:
    """The milestone's actual claim, asserted rather than argued.

    A second format proves the seam only if it takes the same call. If this
    needed another keyword, every published format would have had to grow one
    too, and the endpoint would have needed a column to carry it -- which is
    what "the seam was wrong" would have looked like in practice.
    """
    for body_format in (EnvelopeV1(), CloudEventsV1(source=SOURCE)):
        rendered = body_format.render(**CALL)
        assert rendered.body
        assert rendered.content_type


def test_it_still_renders_the_bytes_it_was_published_with() -> None:
    # The gate. Regenerate with `uv run scripts/generate-format-fixtures
    # tests/fixtures/formats`; if that changes a checked-in file, the edit is a
    # new version rather than a fix.
    from tests.format_samples import rendered

    expected = (FIXTURES / "cloudevents-v1.json").read_bytes()
    assert rendered("cloudevents-v1.json") == expected


def test_the_fixture_is_not_vacuous() -> None:
    # A golden test passes against an empty file if the renderer returns
    # nothing, and against any file if the sample cannot reorder or escape.
    expected = (FIXTURES / "cloudevents-v1.json").read_bytes()
    assert "Lindström".encode() in expected, "the sample must carry a non-ASCII character"
    assert expected.index(b'"coupon"') < expected.index(b'"currency"'), "keys must be sorted"
    assert b'"specversion":"1.0"' in expected, "the spec version must be on the wire"


def test_the_first_format_renders_what_it_always_did() -> None:
    # Additive by construction is a claim about the *old* fixture, so this is
    # where it gets asserted: publishing a second format must not move a byte
    # of the first. Nothing in envelope_v1 changed, which is the point -- if a
    # later format ever forces a shared change, this is what goes red.
    from tests.format_samples import rendered

    assert rendered("envelope-v1.json") == (FIXTURES / "envelope-v1.json").read_bytes()


class TestAgainstTheSpecificationRatherThanOurselves:
    """Conformance claims, each taken from the specification rather than from us.

    Every other test here compares this renderer to itself or to its own
    fixture, which proves agreement and not conformance -- the same distinction
    the signing tests make by verifying against the Standard Webhooks example
    instead of round-tripping our own signer. These are the claims the word
    "CloudEvents" makes to a consumer, written down where they can go red:

    * the JSON format, on the media type and the shape of ``data``
      https://github.com/cloudevents/spec/blob/main/cloudevents/formats/json-format.md
    * the HTTP binding, on the structured-mode content type
      https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/http-protocol-binding.md
    """

    #: REQUIRED for every CloudEvent, per the core specification.
    REQUIRED_ATTRIBUTES = ("specversion", "id", "source", "type")

    def test_every_required_attribute_is_present_and_carries_something(self) -> None:
        document = json.loads(CloudEventsV1(source=SOURCE).render(**CALL).body)
        for attribute in self.REQUIRED_ATTRIBUTES:
            assert document[attribute], f"{attribute} is REQUIRED and must be non-empty"

    def test_the_content_type_is_the_bindings_own_example_string(self) -> None:
        # Copied from the HTTP binding's structured-mode example rather than
        # assembled here, down to the spelling of the charset parameter.
        rendered = CloudEventsV1(source=SOURCE).render(**CALL)
        assert rendered.content_type == "application/cloudevents+json; charset=UTF-8"
        assert rendered.content_type.split(";")[0] == "application/cloudevents+json"

    def test_data_is_a_json_value_rather_than_a_string(self) -> None:
        # The format says data is carried as a JSON value when the content type
        # declares JSON, and as a string otherwise. Serialising the payload to a
        # string and putting *that* in `data` is the ordinary way to get this
        # wrong, and it round-trips through our own parser perfectly well.
        document = json.loads(CloudEventsV1(source=SOURCE).render(**CALL).body)
        assert document["datacontenttype"] == "application/json"
        assert isinstance(document["data"], dict)

    def test_no_attribute_is_invented(self) -> None:
        # A consumer validating against the spec's schema rejects an unknown
        # member. Extension attributes are allowed, but an accidental one is not
        # an extension -- it is a typo that only a strict consumer will find.
        document = json.loads(CloudEventsV1(source=SOURCE).render(**CALL).body)
        allowed = {*self.REQUIRED_ATTRIBUTES, "time", "datacontenttype", "data"}
        assert set(document) <= allowed, f"unknown members: {set(document) - allowed}"
