from __future__ import annotations

from django_domain_events import fire

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.endpoint_recovered import EndpointRecovered


def note_successful_delivery(endpoint: Endpoint) -> None:
    """Reset the dead-delivery count after a delivery lands, and say so if it was failing."""
    recovered = Endpoint.objects.filter(pk=endpoint.pk, consecutive_dead_deliveries__gt=0).update(
        consecutive_dead_deliveries=0
    )
    if recovered:
        fire(EndpointRecovered(endpoint_id=endpoint.pk, endpoint_name=endpoint.name))
