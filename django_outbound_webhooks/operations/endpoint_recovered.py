from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointRecovered:
    """A delivery succeeded to an endpoint that had dead deliveries in a row."""

    #: The endpoint that delivered.
    endpoint_id: int

    #: What the customer calls it, as the delivery that succeeded saw it.
    endpoint_name: str
