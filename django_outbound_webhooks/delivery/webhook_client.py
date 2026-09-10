"""The HTTP client one delivery is sent with."""

from __future__ import annotations

import httpx2

from django_outbound_webhooks.settings import setting


def webhook_client() -> httpx2.Client:
    """A client configured for posting to a stranger's server.

    ``httpx2`` rather than ``httpx``: it is the maintained line, and the
    request-forgery policy that lands in 0.2.0 is a transport concern, so the
    seam it needs has to exist before there is anything to plug into it.

    Redirects are followed but capped. A customer's endpoint answering with one
    has been misconfigured, and following the chain is how a delivery ends up at
    a host nobody registered -- which is the same hole the forgery policy exists
    to close, reached the long way round.
    """
    return httpx2.Client(
        timeout=setting("TIMEOUT_SECONDS"),
        follow_redirects=True,
        max_redirects=setting("MAX_REDIRECTS"),
        headers={"user-agent": "django-outbound-webhooks"},
    )
