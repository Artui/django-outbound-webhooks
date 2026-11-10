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
    """A ``Retrying`` for one delivery, built fresh each time."""
    return Retrying(
        stop=stop_before_delay(
            lease_deadline(
                lease_seconds=lease_seconds,
                timeout_seconds=setting("TIMEOUT_SECONDS"),
                margin_seconds=setting("LEASE_MARGIN_SECONDS"),
            )
        ),
        wait=wait_exponential(multiplier=setting("INNER_BACKOFF_BASE_SECONDS")),
        retry=retry_if_result(
            lambda outcome: (
                outcome.verdict is DeliveryVerdict.RETRY and outcome.retry_after_seconds is None
            )
        ),
        before_sleep=before_sleep,
        retry_error_callback=lambda state: (
            state.outcome.result()
            if state.outcome is not None and not state.outcome.failed
            else DeliveryVerdict.RETRY
        ),
    )
