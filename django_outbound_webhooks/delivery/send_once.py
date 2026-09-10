"""One HTTP attempt at one delivery."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx2

from django_outbound_webhooks.delivery.classify_response import classify_response
from django_outbound_webhooks.signing.sign_request import sign_request
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.rendered_body import RenderedBody


def send_once(
    *,
    client: httpx2.Client,
    url: str,
    secrets: list[str],
    message_id: str,
    body: RenderedBody,
) -> DeliveryVerdict:
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

    try:
        response = client.post(url, content=body.body, headers=headers)
    except httpx2.HTTPError:
        return DeliveryVerdict.RETRY

    return classify_response(response.status_code)
