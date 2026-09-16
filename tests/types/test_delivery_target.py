"""The frozen recipe a delivery row carries as its target."""

from __future__ import annotations

import json

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


def test_the_longest_possible_target_fits_the_substrate_column() -> None:
    """An endpoint's format name is at most 100 characters and a message id is a
    UUID; the substrate refuses a target over 255 inside the firing transaction."""
    longest = DeliveryTarget(
        endpoint_id=2**63 - 1,
        format_name="f" * 100,
        format_version=32767,
        message_id="0" * 36,
    )
    assert len(longest.encode()) <= 255
    assert json.loads(longest.encode())["endpoint"] == 2**63 - 1
