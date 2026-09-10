"""Send one delivery, retrying inside the lease."""

from __future__ import annotations

import httpx2

from django_outbound_webhooks.delivery.retry_policy import retry_policy
from django_outbound_webhooks.delivery.send_once import send_once
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict
from django_outbound_webhooks.types.rendered_body import RenderedBody


def send_webhook(
    *,
    client: httpx2.Client,
    url: str,
    secrets: list[str],
    message_id: str,
    body: RenderedBody,
    lease_seconds: float,
) -> DeliveryVerdict:
    """Attempt the delivery until it succeeds, is refused, or the lease runs low.

    Returns a verdict rather than raising. The caller is a durable receiver, and
    what it does with a failure is a different decision from what happened on the
    wire -- keeping the two apart is what lets the delivery log record "the
    endpoint is gone" rather than "something raised".

    Every attempt sends the same bytes under the same ``webhook-id``, because the
    body is rendered once by the caller and passed in.
    """
    # The callable form rather than the iterator form. The iterator requires the
    # caller to push each result back into the retry state by hand, which is
    # where a result-based policy silently becomes a no-retry policy if the push
    # is forgotten. Here tenacity owns the loop and the result is just a return
    # value.
    #
    # `retry_error_callback` on the policy turns "ran out of time" into the last
    # verdict rather than a RetryError, so this always yields a verdict.
    return retry_policy(lease_seconds=lease_seconds)(
        send_once,
        client=client,
        url=url,
        secrets=secrets,
        message_id=message_id,
        body=body,
    )
