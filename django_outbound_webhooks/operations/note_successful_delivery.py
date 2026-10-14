"""Forget an endpoint's failures once it answers again."""

from __future__ import annotations

from django_domain_events import fire

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.endpoint_recovered import EndpointRecovered


def note_successful_delivery(endpoint: Endpoint) -> None:
    """Reset the dead-delivery count after a delivery lands, and say so if it was failing.

    "Sustained" is the whole content of auto-disable: an endpoint that fails
    nineteen times over a month and succeeds in between is a flaky network, and
    an endpoint that fails nineteen times in a row is gone. Without this reset
    the threshold would count *lifetime* failures and disable every endpoint
    eventually, including one that has never had a bad week.

    The filter carries the condition instead of an ``if``, so the ordinary
    case -- an endpoint already at zero, which is almost every delivery --
    touches no row. It is still one statement either way: a read to decide
    whether to write would be a statement too, and a slower one, since it would
    make the decision in this process and leave room for another worker to
    change the answer in between. The first draft of this docstring claimed the
    ordinary case cost nothing at all, and the test below is what disagreed.

    **That same update is what decides ``EndpointRecovered``.** It matches a row
    only when the endpoint was failing, so the number of rows it changed is the
    answer, and among several deliveries landing together exactly one can
    change it. The event is fired from that answer with no read: the endpoint is
    handed in by the delivery, which loaded it to send the request.

    Called inside the delivery's transaction, where ``fire()`` expects to be, so
    a delivery rolled back because its worker lost the row takes the reset and
    the event with it.
    """
    recovered = Endpoint.objects.filter(pk=endpoint.pk, consecutive_dead_deliveries__gt=0).update(
        consecutive_dead_deliveries=0
    )
    if recovered:
        fire(EndpointRecovered(endpoint_id=endpoint.pk, endpoint_name=endpoint.name))
