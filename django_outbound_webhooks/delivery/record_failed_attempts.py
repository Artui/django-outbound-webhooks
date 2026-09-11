"""The substrate's failure hook, writing what the receiver could not."""

from __future__ import annotations

import logging

from django_domain_events import DeliveryFailure

from django_outbound_webhooks.delivery.pending_attempts import pending_attempts
from django_outbound_webhooks.delivery.record_attempts import record_attempts

logger = logging.getLogger(__name__)


def record_failed_attempts(failure: DeliveryFailure) -> None:
    """Write the attempts of a delivery that failed.

    Runs outside the transaction the receiver's raise rolled back, which is the
    only reason a failed delivery can be logged at all. Everything the receiver
    wrote is already gone by the time this runs; what survives is the context
    variable it filled, because that lives in memory rather than in the database.

    A delivery that failed before making any request leaves nothing to write --
    a deleted endpoint, a pruned event, a format that was never published. The
    substrate's own row already records those with the exception's message, so
    writing an empty attempt here would invent a request that was never made.
    """
    pending = pending_attempts.get()
    if pending is None:
        return

    # No second clause for "set but empty". It was written and removed: mutating
    # it out changed nothing, because an empty outcome list already produces no
    # rows. A guard that cannot fail is one that gets trusted for a reason it
    # does not have.

    try:
        record_attempts(pending)
    finally:
        pending_attempts.set(None)
