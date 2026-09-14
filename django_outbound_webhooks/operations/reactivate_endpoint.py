"""Switch an auto-disabled endpoint back on, once somebody has fixed it."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def reactivate_endpoint(endpoint: Endpoint) -> Endpoint:
    """Re-enable an endpoint and clear what disabled it.

    The count has to be cleared with the flag, and that is the whole reason this
    exists rather than leaving callers to set ``is_active``. An endpoint
    re-enabled with its count still at the threshold is disabled again by its
    very next dead delivery, which looks exactly like the re-enabling having
    silently failed -- and the operator's next move is to try again.

    ``disabled_at`` is cleared too, because it answers "did we switch this off,
    or did somebody?" and a stale value makes an endpoint somebody re-enabled
    look auto-disabled forever.

    Deliberately not fussy about the endpoint's current state: re-enabling an
    active endpoint is a no-op that still clears a count, which is a reasonable
    thing to want after a customer has fixed their receiver.
    """
    endpoint.is_active = True
    endpoint.disabled_at = None
    endpoint.consecutive_dead_deliveries = 0
    endpoint.save(
        update_fields=["is_active", "disabled_at", "consecutive_dead_deliveries", "updated_at"]
    )
    return endpoint
