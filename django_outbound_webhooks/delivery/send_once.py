from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx2

from django_outbound_webhooks.delivery.classify_response import classify_response
from django_outbound_webhooks.delivery.retry_after_seconds import (
    HONOURED_STATUSES,
    retry_after_seconds,
)
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.sign_request import sign_request
from django_outbound_webhooks.types.attempt_outcome import AttemptOutcome
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.rendered_body import RenderedBody


def send_once(
    *,
    client: httpx2.Client,
    url: str,
    secrets: list[str],
    message_id: str,
    body: RenderedBody,
) -> AttemptOutcome:
    """Post the body once and read the answer as a verdict."""
    headers = sign_request(
        secrets=secrets,
        message_id=message_id,
        timestamp=datetime.now(tz=timezone.utc),
        body=body.body,
    )
    headers["content-type"] = body.content_type

    started = time.monotonic()
    try:
        response = client.post(url, content=body.body, headers=headers)
    except httpx2.HTTPError as exc:
        return AttemptOutcome(
            verdict=DeliveryVerdict.RETRY,
            duration_ms=_elapsed_ms(started),
            error=f"{type(exc).__name__}: {exc}"[: setting("LOG_BODY_CHARS")],
        )

    return AttemptOutcome(
        verdict=classify_response(response.status_code),
        duration_ms=_elapsed_ms(started),
        status_code=response.status_code,
        response_body=response.text[: setting("LOG_BODY_CHARS")],
        retry_after_seconds=(
            retry_after_seconds(
                response.headers.get("retry-after"), now=datetime.now(tz=timezone.utc)
            )
            if response.status_code in HONOURED_STATUSES
            else None
        ),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
