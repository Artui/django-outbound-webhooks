"""The inner retry tier: one HTTP request, bounded by the lease."""

from __future__ import annotations

from collections.abc import Callable

from tenacity import Retrying, retry_if_result, stop_before_delay, wait_exponential

from django_outbound_webhooks.delivery.lease_deadline import lease_deadline
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict


def retry_policy(
    *,
    lease_seconds: float,
    before_sleep: Callable[..., None] | None = None,
) -> Retrying:
    """A ``Retrying`` for one delivery, built fresh each time.

    Built per delivery rather than as a ``@retry`` decorator. The timeout and the
    lease are per-endpoint and per-receiver values, and a decorator fixes its
    policy at import time; the explicit object also keeps retrying out of the
    receiver's signature, which matters because the receiver is the thing the
    substrate calls.

    ``stop_before_delay`` rather than ``stop_after_delay``, and rather than
    ``stop_after_attempt``. The count is unbounded in *time*, which is the
    dimension the lease measures. ``stop_after_delay`` only notices a limit once
    it has been crossed, where this one refuses to start an attempt that would
    cross it -- and the difference between those two is a delivery that was sent
    and never recorded.

    ``retry_if_result`` is the classification the substrate does not have. A
    webhook's verdict is a status code, so it arrives as a **return value**; the
    substrate can only retry what raises, which is why it retries everything to
    the attempt budget and no receiver can say `410 Gone` is permanent. Here a
    permanent verdict simply stops.
    """
    return Retrying(
        stop=stop_before_delay(
            lease_deadline(
                lease_seconds=lease_seconds,
                timeout_seconds=setting("TIMEOUT_SECONDS"),
                margin_seconds=setting("LEASE_MARGIN_SECONDS"),
            )
        ),
        wait=wait_exponential(multiplier=setting("INNER_BACKOFF_BASE_SECONDS")),
        retry=retry_if_result(lambda outcome: outcome.verdict is DeliveryVerdict.RETRY),
        before_sleep=before_sleep,
        # The caller reads the last outcome rather than catching RetryError.
        # Returning the verdict keeps "ran out of time" and "endpoint said no"
        # distinguishable, which a raised RetryError would flatten.
        retry_error_callback=lambda state: (
            state.outcome.result()
            if state.outcome is not None and not state.outcome.failed
            else DeliveryVerdict.RETRY
        ),
    )
