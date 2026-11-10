from __future__ import annotations

import logging

from django_domain_events import DeliveryFailure, DeliveryStatus

from django_outbound_webhooks.delivery.pending_attempts import pending_attempts
from django_outbound_webhooks.delivery.record_attempts import record_attempts
from django_outbound_webhooks.operations.note_dead_delivery import note_dead_delivery

logger = logging.getLogger(__name__)


def record_failed_attempts(failure: DeliveryFailure) -> None:
    """Write the attempts of a delivery that failed."""
    pending = pending_attempts.get()
    if pending is None:
        return

    try:
        record_attempts(pending)
        if failure.status is DeliveryStatus.DEAD:
            note_dead_delivery(pending.target.endpoint_id)
    finally:
        pending_attempts.set(None)
