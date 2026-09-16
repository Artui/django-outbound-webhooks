"""The substrate's failure hook, writing what the receiver could not."""

from __future__ import annotations

import logging

from django_domain_events import DeliveryFailure, DeliveryStatus

from django_outbound_webhooks.delivery.pending_attempts import pending_attempts
from django_outbound_webhooks.delivery.record_attempts import record_attempts
from django_outbound_webhooks.operations.note_dead_delivery import note_dead_delivery

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
        if failure.status is DeliveryStatus.DEAD:
            # Only DEAD, and only here. A FAILED delivery will be tried again,
            # so counting it would measure the substrate's patience rather than
            # the endpoint's health -- one rotted endpoint would cross any
            # threshold inside a single delivery's retries.
            #
            # Reached only when a request was actually made, which is the right
            # place for it to be reached: an early return above covers the
            # deliveries that died without one -- a deleted endpoint, a pruned
            # event, an unpublished format -- and none of those is evidence
            # about whether the customer's endpoint is answering.
            note_dead_delivery(pending.target.endpoint_id)
    finally:
        pending_attempts.set(None)
