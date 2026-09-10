"""Whether a response is worth another attempt."""

from __future__ import annotations

from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict

#: Statuses that mean "later", not "no". 408 and 429 are the endpoint asking for
#: time; 5xx is it failing in a way it may well recover from.
RETRYABLE_STATUSES = frozenset({408, 429})


def classify_response(status_code: int) -> DeliveryVerdict:
    """Read one HTTP status as a verdict.

    The 4xx split is the point. ``410 Gone`` is the specification's way for a
    consumer to say the endpoint is retired, and retrying it is pure waste --
    but so is retrying a 400 or a 403, because a body that was malformed or a
    credential that was refused will be exactly the same on the next attempt.
    So 4xx is permanent apart from the two statuses that explicitly mean "later".

    ``1xx`` and ``3xx`` are treated as permanent rather than retried. A webhook
    endpoint answering with either has been misconfigured, and misconfiguration
    does not heal on a retry -- the client follows redirects itself, so a 3xx
    reaching here means the redirect budget ran out.
    """
    if 200 <= status_code < 300:
        return DeliveryVerdict.SUCCEEDED
    if status_code in RETRYABLE_STATUSES:
        return DeliveryVerdict.RETRY
    if 500 <= status_code < 600:
        return DeliveryVerdict.RETRY
    return DeliveryVerdict.PERMANENT
