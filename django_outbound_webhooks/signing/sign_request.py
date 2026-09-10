"""Signature headers for one delivery, to the Standard Webhooks specification."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from math import floor

from standardwebhooks import Webhook


def sign_request(
    *,
    secrets: Sequence[str],
    message_id: str,
    timestamp: datetime,
    body: bytes,
) -> dict[str, str]:
    """The three headers a conforming receiver verifies.

    ``secrets`` is a sequence rather than one value because the specification
    carries several signatures in one space-separated header, and that *is* the
    secret-rotation overlap: sign with the outgoing and incoming secret at once
    and every conforming receiver accepts either, with no coordinated cutover.
    One secret is the ordinary case and the same code path.

    Two things are done here rather than left to the library, and both are
    corrections rather than preferences.

    First, the timestamp is converted to UTC. ``Webhook.sign`` calls
    ``timestamp.replace(tzinfo=timezone.utc)``, which *forces* the zone instead
    of converting: an aware datetime at +02:00 keeps its wall clock and moves
    two hours in absolute time, and a naive one is read as UTC whatever the
    server's zone. Either way the signed timestamp is wrong by a whole number of
    hours, and the only symptom is that receivers reject the delivery as too old
    or too new -- a signature failure with a correct signature in it.

    Second, the header's timestamp is derived from the same converted value the
    signature is computed over. Deriving it twice is how the two come to
    disagree, and a mismatch there fails verification for every receiver while
    every local test of the signer passes.
    """
    if not secrets:
        raise ValueError("A delivery needs at least one signing secret.")

    if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
        raise ValueError(
            "sign_request needs an aware datetime. A naive one would be signed as though it "
            "were UTC, so the delivery would carry a timestamp wrong by the server's offset."
        )

    signed_at = timestamp.astimezone(timezone.utc)

    try:
        payload = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        # The specification signs `{id}.{timestamp}.{body}` as one UTF-8 string,
        # so a body that is not UTF-8 cannot be signed to the spec at all.
        # Refusing here names the reason; letting it through would mean
        # inventing a signature format, which is the one thing adopting a
        # specification is meant to avoid.
        raise ValueError(
            "Only a UTF-8 body can be signed to the Standard Webhooks specification, which "
            "signs the body as text. A binary format needs a different signing scheme."
        ) from exc

    signatures = " ".join(
        Webhook(secret).sign(msg_id=message_id, timestamp=signed_at, data=payload)
        for secret in secrets
    )
    return {
        "webhook-id": message_id,
        "webhook-timestamp": str(floor(signed_at.timestamp())),
        "webhook-signature": signatures,
    }
