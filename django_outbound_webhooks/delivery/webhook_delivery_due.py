"""The per-endpoint event that carries one delivery."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class WebhookDeliveryDue:
    """One customer's copy of one domain event, owed to one endpoint.

    This is the fan-out, and it is the substrate's own idiom rather than a
    workaround. A delivery row is written per *registered* receiver, keyed by a
    string the registry holds from import time, so a row per endpoint would need
    a receiver key invented at fire time -- which the registry refuses. Firing a
    second event per endpoint gets the same shape from the other direction, and
    every one of them arrives with its own delivery row, its own attempt count,
    its own backoff, its own dead-letter and its own replay.

    The cost is stated rather than discovered: one domain event with forty
    subscribed endpoints writes forty-one event rows, so retention is a sizing
    decision rather than a formality.

    Everything needed to render is frozen here, which is the recipe rather than
    the bytes. The endpoint's pinned format could be edited between the fan-out
    and a retry, and re-reading it then would change what an already-integrated
    consumer receives under a signature that still verifies.
    """

    #: The endpoint row this copy is for.
    endpoint_id: int

    #: The domain event being delivered. Its payload and timestamp are read back
    #: from the log at delivery time, which is safe because an event row is
    #: written once and never edited.
    source_event_id: int

    #: The format identity as it stood when this was fanned out.
    format_name: str
    format_version: int

    #: The stable ``webhook-id``. Generated once, here, because a receiver
    #: deduplicates on it: every attempt of this delivery, inner or outer, has
    #: to present the same one.
    message_id: str
