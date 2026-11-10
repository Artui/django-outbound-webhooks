from __future__ import annotations

from django_outbound_webhooks.delivery.pending_attempts import PendingAttempts
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt


def record_attempts(pending: PendingAttempts) -> int:
    """Write a row per HTTP request, and return how many."""
    rows = [
        DeliveryAttempt(
            message_id=pending.target.message_id,
            endpoint_id=pending.target.endpoint_id,
            url=pending.url,
            source_event_id=pending.source_event_id,
            format_name=pending.target.format_name,
            format_version=pending.target.format_version,
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
