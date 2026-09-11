"""Write one delivery's attempts to the log."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_outbound_webhooks.delivery.pending_attempts import PendingAttempts


def record_attempts(pending: PendingAttempts) -> int:
    """Write a row per HTTP request, and return how many.

    Called from two places that cannot be merged: the receiver itself when the
    delivery succeeded, and the substrate's failure hook when it did not. The
    split is not tidiness -- a receiver's writes are discarded the moment it
    raises, so the attempts most worth recording are the ones it cannot record.
    """
    from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt

    rows = [
        DeliveryAttempt(
            message_id=pending.due.message_id,
            endpoint_id=pending.due.endpoint_id,
            url=pending.url,
            source_event_id=pending.due.source_event_id,
            format_name=pending.due.format_name,
            format_version=pending.due.format_version,
            outer_attempt=pending.outer_attempt,
            inner_attempt=index,
            request_body_sha256=pending.request_body_sha256,
            request_body_bytes=pending.request_body_bytes,
            response_status=outcome.status_code,
            response_body=outcome.response_body,
            error=outcome.error,
            duration_ms=outcome.duration_ms,
            verdict=outcome.verdict.value,
        )
        for index, outcome in enumerate(pending.outcomes, start=1)
    ]
    DeliveryAttempt.objects.bulk_create(rows)
    return len(rows)
