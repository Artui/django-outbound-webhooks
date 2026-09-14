"""Forget an endpoint's failures once it answers again."""

from __future__ import annotations


def note_successful_delivery(endpoint_id: int) -> None:
    """Reset the dead-delivery count after a delivery lands.

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
    """
    # Inside the function, like every model import in this package. Django
    # imports an app's package before the app registry is ready, so a
    # module-scope model import anywhere reachable from the package root raises
    # AppRegistryNotReady. This module is not re-exported today, which makes the
    # rule look optional here -- it is not: keeping it uniform is what stops a
    # re-export added later from breaking the package's importability, which is
    # a failure that surfaces nowhere near the line that caused it.
    from django_outbound_webhooks.models.endpoint import Endpoint

    Endpoint.objects.filter(pk=endpoint_id, consecutive_dead_deliveries__gt=0).update(
        consecutive_dead_deliveries=0
    )
