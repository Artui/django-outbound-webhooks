"""The event fired when an endpoint's deliveries start dying."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class EndpointFailing:
    """An endpoint's first dead delivery since it last delivered successfully.

    The warning before ``EndpointDisabled``, and often the only warning there
    is. Auto-disable acts after a run of dead deliveries, and a run is measured
    in the customer's traffic rather than in time: twenty deliveries dying
    together cross it inside one attempt budget, while an endpoint receiving a
    few events a week takes weeks. Either way, without this the first thing
    anybody hears is that the endpoint is already off - and with
    ``AUTO_DISABLE_AFTER_DEAD_DELIVERIES`` set to ``None`` they would hear
    nothing at all, which is why it fires in that configuration too.

    **Once per incident, never once per delivery.** It fires when the count of
    consecutive dead deliveries goes from zero to one, and not again until a
    delivery succeeds and ``EndpointRecovered`` has reset it. A customer is
    told their integration is failing, not how many times.

    Never delivered to customer endpoints, for the reason ``EndpointDisabled``
    is not: a customer subscribed to it would hear about everybody else's
    integrations failing, while their own failing endpoint is the one least
    likely to receive the news.
    """

    #: The endpoint whose delivery died. An id rather than the row, because the
    #: event is read back long after it was written.
    endpoint_id: int

    #: What the customer calls it, frozen now, so the event still reads as a
    #: sentence once the row has been renamed or deleted.
    endpoint_name: str

    #: How many consecutive dead deliveries switch it off, as configured when
    #: this fired, or None when nothing will. Named for its tier, like the
    #: setting it is read from: each is a delivery that spent its whole attempt
    #: budget, not an HTTP request. It is what lets a notification say "and will
    #: be switched off after twenty" without reading this package's settings.
    disabled_after_dead_deliveries: int | None
