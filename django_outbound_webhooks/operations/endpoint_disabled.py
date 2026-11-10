from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointDisabled:
    """One endpoint auto-disabled after sustained failure."""

    #: The endpoint that was disabled.
    endpoint_id: int

    #: What the customer calls it, frozen when disabled, so events still read.
    endpoint_name: str

    dead_deliveries: int
