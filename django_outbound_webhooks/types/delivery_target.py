"""One endpoint's copy of one event, as the delivery row names it."""

from __future__ import annotations

import json
from dataclasses import dataclass

FORMAT_NAME_MAX_ENCODED_LENGTH = 100
"""The longest a format name may be once a delivery target has encoded it.

With the other fields at their widest - a 64-bit endpoint id, a 16-bit version,
a UUID message id - this leaves a target inside the substrate's 255 characters.
"""


def encoded_format_name_length(name: str) -> int:
    """How many characters ``name`` occupies inside an encoded target."""
    return len(json.dumps(name, ensure_ascii=False)) - 2


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    """Everything a delivery needs that must not change between its attempts.

    The substrate writes one delivery row per target a receiver names, and hands
    the target back on every attempt as ``DeliveryContext.target``. So the
    target is where a delivery's recipe is frozen, and it is frozen at fire
    time, in the transaction that recorded the event.

    **The format is frozen here rather than read at delivery.** An operator
    re-pinning an endpoint between the first attempt and a retry must not change
    what an already-integrated consumer receives, under a signature that still
    verifies.

    **The message id is minted here, once.** A receiver deduplicates on
    ``webhook-id``, so every attempt of one delivery has to present the same
    one - and a replay has to present a new one, which is why it is random
    rather than derived from anything a replay would repeat.

    Encoded as compact JSON rather than a delimited string, because a format
    name is operator-chosen text and the one thing a delimiter cannot promise is
    that the text never contains it.

    **The substrate refuses a target over 255 characters inside the transaction
    that fired the event**, so an overlong one fails the caller's business change
    for every event the endpoint subscribes to. The length is therefore bounded
    where a name enters, not here: ``FormatRegistry.register`` refuses a name
    whose encoded form is longer than ``FORMAT_NAME_MAX_ENCODED_LENGTH``, and a
    customer can only pin a registered name. The bound is on the *encoded*
    length because the column's is: a quote encodes as two characters and a
    control character as six, so a 100-character name is not a 100-character
    field. Non-ASCII is written as itself for the same reason, since escaping it
    would cost six characters a letter.
    """

    endpoint_id: int
    format_name: str
    format_version: int
    message_id: str

    def encode(self) -> str:
        return json.dumps(
            {
                "endpoint": self.endpoint_id,
                "format": self.format_name,
                "version": self.format_version,
                "message": self.message_id,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @classmethod
    def decode(cls, target: str) -> DeliveryTarget:
        fields = json.loads(target)
        return cls(
            endpoint_id=fields["endpoint"],
            format_name=fields["format"],
            format_version=fields["version"],
            message_id=fields["message"],
        )
