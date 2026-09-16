"""The event fired when a failing endpoint delivers again."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointRecovered:
    """A delivery succeeded to an endpoint that had dead deliveries in a row.

    The other end of ``EndpointFailing``, so an incident that was announced is
    also closed: a notification sent on the way in has a matching one on the
    way out, and whatever opened a ticket can resolve it.

    **Once per incident**, for the same reason as its pair: it fires on the
    delivery that resets the count, and only that one. The reset was already a
    single update that touches the row only when the endpoint *was* failing, so
    the event rides on that update and costs no read.

    It fires inside the delivery's own transaction, so a delivery rolled back
    because its worker lost the row takes the event with it.

    ``reactivate_endpoint`` does not fire it. Switching an endpoint back on is
    somebody's decision that it deserves another chance, not evidence that it
    answers; the first delivery that lands afterwards is.

    Never delivered to customer endpoints, for the reason its pair is not.
    """

    #: The endpoint that delivered. An id rather than the row, for the same
    #: reason as its pair.
    endpoint_id: int

    #: What the customer calls it, as the delivery that succeeded saw it.
    endpoint_name: str
