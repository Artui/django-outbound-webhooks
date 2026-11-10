from __future__ import annotations

import httpx2

from django_outbound_webhooks.delivery.pinning_transport import PinningTransport
from django_outbound_webhooks.settings import setting


def webhook_client() -> httpx2.Client:
    """A client configured for posting to a stranger's server."""
    return httpx2.Client(
        transport=PinningTransport(httpx2.HTTPTransport()),
        timeout=setting("TIMEOUT_SECONDS"),
        follow_redirects=True,
        max_redirects=setting("MAX_REDIRECTS"),
        headers={"user-agent": "django-outbound-webhooks"},
    )
