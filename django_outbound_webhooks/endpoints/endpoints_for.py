from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db.models import QuerySet

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.settings import setting


def endpoints_for(*, event_name: str, scope: Mapping[str, Any]) -> QuerySet[Endpoint]:
    """The active endpoints subscribed to this event, within its tenant."""
    subscribed = Endpoint.objects.filter(is_active=True, subscriptions__event_name=event_name)

    tenant_key = setting("TENANT_SCOPE_KEY")
    if tenant_key is None:
        return subscribed

    value = scope.get(tenant_key)
    if value is None or value == "":
        return Endpoint.objects.none()

    return subscribed.filter(tenant=value)
