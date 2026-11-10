from __future__ import annotations

from django_outbound_webhooks.models.endpoint import Endpoint


def reactivate_endpoint(endpoint: Endpoint) -> Endpoint:
    """Re-enable an endpoint and clear what disabled it."""
    endpoint.is_active = True
    endpoint.disabled_at = None
    endpoint.consecutive_dead_deliveries = 0
    endpoint.save(
        update_fields=["is_active", "disabled_at", "consecutive_dead_deliveries", "updated_at"]
    )
    return endpoint
