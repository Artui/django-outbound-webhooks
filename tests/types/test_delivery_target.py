"""The frozen recipe a delivery row carries as its target."""

from __future__ import annotations

from django_outbound_webhooks.types.delivery_target import DeliveryTarget

TARGET = DeliveryTarget(
    endpoint_id=42, format_name="envelope", format_version=1, message_id="msg_abc"
)


def test_it_round_trips() -> None:
    assert DeliveryTarget.decode(TARGET.encode()) == TARGET


def test_the_encoding_is_compact_readable_json() -> None:
    """An operator reads it in the substrate's admin, and a delimiter could not
    promise an operator-chosen format name never contains it."""
    assert TARGET.encode() == (
        '{"endpoint":42,"format":"envelope","version":1,"message":"msg_abc"}'
    )


def test_a_format_name_with_punctuation_survives() -> None:
    odd = DeliveryTarget(endpoint_id=1, format_name='a:b,"c" d', format_version=2, message_id="m")
    assert DeliveryTarget.decode(odd.encode()) == odd
