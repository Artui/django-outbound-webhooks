from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointFailing:
    """An endpoint's first dead delivery since it last delivered successfully."""

    #: The endpoint whose delivery died.
    endpoint_id: int

    #: What the customer calls it, frozen now, so events still read once it is gone.
    endpoint_name: str

    disabled_after_dead_deliveries: int | None
