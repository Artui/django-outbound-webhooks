"""The event fired when this package switches an endpoint off."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointDisabled:
    """One endpoint auto-disabled after sustained failure.

    A domain event rather than a log line, and the reason is that somebody has
    to tell the customer. Disabling an endpoint is the moment their integration
    stops, so an operator wants to email them, open a ticket, or show a banner
    -- and every one of those is code somebody else writes, in an app this
    package has never heard of. An event is how anything else in the deployment
    learns something happened here, and this deployment already has an event
    log, ordered and durable and replayable, because this package requires one.

    It is never delivered to customer endpoints, even one subscribed to it by
    name - ``INTERNAL_EVENTS`` in ``delivery_targets`` - which reads like an
    omission and is the opposite. The one endpoint most obviously interested in this event is
    the one it is about, and that endpoint has just been switched off; a
    customer subscribed to it would be told about every *other* endpoint's
    failures instead, which is somebody else's operational detail arriving over
    their webhook.
    """

    #: The endpoint that was disabled. An id rather than the row, because the
    #: event is read back long after it was written and the row it names may
    #: have been edited or deleted since.
    endpoint_id: int

    #: What the customer calls it, frozen at the moment it was disabled, so the
    #: event still reads as a sentence once the row is gone.
    endpoint_name: str

    #: How many consecutive dead deliveries it took. Named for the tier it
    #: counts, like the column it is read from.
    dead_deliveries: int
