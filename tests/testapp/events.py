"""Domain events a consumer of this package would declare."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class OrderPlaced:
    order_id: int
    total_cents: int


@event
@dataclass(frozen=True)
class OrderShipped:
    order_id: int
