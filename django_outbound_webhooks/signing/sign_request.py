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
    """The three headers a conforming receiver verifies."""
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
