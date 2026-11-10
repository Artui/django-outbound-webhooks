from __future__ import annotations

from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict

#: Statuses that mean "later", not "no". 408 and 429 are the endpoint asking for
#: time; 5xx is it failing in a way it may well recover from.
RETRYABLE_STATUSES = frozenset({408, 429})


def classify_response(status_code: int) -> DeliveryVerdict:
    """Read one HTTP status as a verdict."""
    if 200 <= status_code < 300:
        return DeliveryVerdict.SUCCEEDED
    if status_code in RETRYABLE_STATUSES:
        return DeliveryVerdict.RETRY
    if 500 <= status_code < 600:
        return DeliveryVerdict.RETRY
    return DeliveryVerdict.PERMANENT
