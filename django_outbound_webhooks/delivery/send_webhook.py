from __future__ import annotations

import httpx2

from django_outbound_webhooks.delivery.retry_policy import retry_policy
from django_outbound_webhooks.delivery.send_once import send_once
from django_outbound_webhooks.types.attempt_outcome import AttemptOutcome
from django_outbound_webhooks.types.rendered_body import RenderedBody


def send_webhook(
    *,
    client: httpx2.Client,
    url: str,
    secrets: list[str],
    message_id: str,
    body: RenderedBody,
    lease_seconds: float,
    history: list[AttemptOutcome],
) -> AttemptOutcome:
    """Attempt the delivery until it succeeds, is refused, or the lease runs low."""

    # The callable form rather than the iterator form.
    def attempt() -> AttemptOutcome:
        outcome = send_once(
            client=client, url=url, secrets=secrets, message_id=message_id, body=body
        )
        history.append(outcome)
        return outcome

    return retry_policy(lease_seconds=lease_seconds)(attempt)
