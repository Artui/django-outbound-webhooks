"""Count a delivery the substrate gave up on, and disable a rotted endpoint."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django_domain_events import fire

from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled
from django_outbound_webhooks.settings import setting

logger = logging.getLogger(__name__)


def note_dead_delivery(endpoint_id: int) -> bool:
    """Record one dead delivery against an endpoint; return whether that ended it.

    Called only for ``DEAD``, never for ``FAILED``. A failed delivery will be
    tried again, so counting it would measure how patient the substrate's
    backoff is rather than whether the endpoint is answering: one rotted
    endpoint would cross any threshold within a single delivery's retries.

    The increment is ``F("...") + 1`` rather than a read, an add and a save.
    Several deliveries to one endpoint die in parallel workers as a matter of
    course, and the read-modify-write version loses exactly the increments that
    would have crossed the threshold -- the ones that arrive together, which is
    what sustained failure looks like.

    Returns True only for the call that disabled the endpoint. Later dead
    deliveries against an already-disabled endpoint keep counting and return
    False, because the count is what an operator reads to decide whether it is
    worth re-enabling.
    """
    threshold = setting("AUTO_DISABLE_AFTER_DEAD_DELIVERIES")

    # Inside the function, like every model import in this package. Django
    # imports an app's package before the app registry is ready, so a
    # module-scope model import anywhere reachable from the package root raises
    # AppRegistryNotReady. This module is not re-exported today, which makes the
    # rule look optional here -- it is not: keeping it uniform is what stops a
    # re-export added later from breaking the package's importability, which is
    # a failure that surfaces nowhere near the line that caused it.
    from django_outbound_webhooks.models.endpoint import Endpoint

    # One transaction for the increment, the switch-off and the event. The event
    # is written by fire() into whatever transaction is open, so an
    # EndpointDisabled that committed while the endpoint stayed active would be
    # a durable record of something that never happened.
    with transaction.atomic():
        updated = Endpoint.objects.filter(pk=endpoint_id).update(
            consecutive_dead_deliveries=F("consecutive_dead_deliveries") + 1
        )
        if not updated:
            # Deleted between the delivery and this hook. Nothing to disable and
            # nothing owed: the customer removed the destination themselves.
            return False

        if threshold is None:
            return False

        endpoint = Endpoint.objects.get(pk=endpoint_id)
        if not endpoint.is_active or endpoint.consecutive_dead_deliveries < threshold:
            return False

        endpoint.is_active = False
        endpoint.disabled_at = timezone.now()
        endpoint.save(update_fields=["is_active", "disabled_at", "updated_at"])

        logger.warning(
            "Disabled endpoint %s after %s consecutive dead deliveries.",
            endpoint.name,
            endpoint.consecutive_dead_deliveries,
        )
        fire(
            EndpointDisabled(
                endpoint_id=endpoint.pk,
                endpoint_name=endpoint.name,
                dead_deliveries=endpoint.consecutive_dead_deliveries,
            )
        )
        return True
