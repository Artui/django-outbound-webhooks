"""The frozen recipe a delivery row carries as its target."""

from __future__ import annotations

from typing import Any

import pytest
from django_domain_events.utils import TARGET_MAX_LENGTH

from django_outbound_webhooks.formats.format_registry import FormatRegistry
from django_outbound_webhooks.types.delivery_target import DeliveryTarget
from django_outbound_webhooks.types.rendered_body import RenderedBody


class _Stub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.version = 1

    def render(
        self, *, message_id: str, event_name: str, occurred_at: str, payload: dict[str, Any]
    ) -> RenderedBody:
        return RenderedBody(body=b"{}", content_type="application/json")


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


@pytest.mark.parametrize(
    "format_name",
    [
        "f" * 100,
        # Each of these is as long as registration allows for its kind of
        # character, and each escapes differently: a non-ASCII letter is kept as
        # itself, a quote doubles, and a control character becomes six.
        "\u00e9" * 100,
        '"' * 50,
        "\x01" * 16,
    ],
)
def test_the_longest_target_a_registered_format_allows_fits_the_substrate_column(
    format_name: str,
) -> None:
    """The bound is read off the registry's own rule rather than a hand-picked name.

    A target the substrate refuses is refused inside the transaction that fired
    the event, so an overlong one fails the caller's business change - for every
    event the endpoint is subscribed to. Registration is where a name that could
    do that has to be stopped, so every name here is first shown to be one the
    registry accepts.
    """
    FormatRegistry().register(_Stub(format_name))
    longest = DeliveryTarget(
        endpoint_id=2**63 - 1,
        format_name=format_name,
        format_version=32767,
        message_id="0" * 36,
    )
    assert len(longest.encode()) <= TARGET_MAX_LENGTH
    assert DeliveryTarget.decode(longest.encode()) == longest
