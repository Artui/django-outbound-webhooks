from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django_domain_events import fire

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled
from django_outbound_webhooks.operations.endpoint_failing import EndpointFailing
from django_outbound_webhooks.settings import setting

logger = logging.getLogger(__name__)


def note_dead_delivery(endpoint_id: int) -> bool:
    """Record one dead delivery against an endpoint; return whether that ended it."""
    threshold = setting("AUTO_DISABLE_AFTER_DEAD_DELIVERIES")

    with transaction.atomic():
        started_failing = bool(
            Endpoint.objects.filter(pk=endpoint_id, consecutive_dead_deliveries=0).update(
                consecutive_dead_deliveries=1
            )
        )
        if not started_failing and not Endpoint.objects.filter(pk=endpoint_id).update(
            consecutive_dead_deliveries=F("consecutive_dead_deliveries") + 1
        ):
            return False

        if threshold is None and not started_failing:
            return False

        endpoint = Endpoint.objects.get(pk=endpoint_id)
        if started_failing:
            fire(
                EndpointFailing(
                    endpoint_id=endpoint.pk,
                    endpoint_name=endpoint.name,
                    disabled_after_dead_deliveries=threshold,
                )
            )

        if (
            threshold is None
            or not endpoint.is_active
            or endpoint.consecutive_dead_deliveries < threshold
        ):
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
