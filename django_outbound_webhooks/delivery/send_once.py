"""One HTTP attempt at one delivery."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx2

from django_outbound_webhooks.delivery.classify_response import classify_response
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
    """Post the body once and read the answer as a verdict.

    The body arrives already rendered rather than being rendered here, and that
    is deliberate: every attempt of one delivery has to send **byte-identical**
    content. ``webhook-id`` is stable across attempts and is what a receiver
    deduplicates on, so two different bodies under one id leave the customer in
    a state that depends on which attempt landed.

    The timestamp is fresh on each attempt, which is correct and is the one
    thing that legitimately differs: receivers verify it against a tolerance
    window, so a retry an hour later would be rejected as too old if it reused
    the original.

    Returns the whole outcome rather than a bare verdict, because the delivery
    log needs what the endpoint said and how long it took, and this is the only
    place that knows either.

    A transport error becomes ``RETRY`` rather than propagating. A refused
    connection or a timeout is the most ordinary transient failure there is, and
    letting it raise would hand the decision to the outer tier, which cannot
    tell it apart from a bug in this package.
    """
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
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
