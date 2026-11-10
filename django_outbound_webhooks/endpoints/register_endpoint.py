from __future__ import annotations

from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction

from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.subscription import Subscription
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.types.format_id import FormatId


def register_endpoint(
    *,
    name: str,
    url: str,
    secret: str,
    event_names: Sequence[str],
    tenant: str = "",
    format_name: str | None = None,
    format_version: int | None = None,
) -> Endpoint:
    """The supported way to add an endpoint, and the door the rules live behind."""
    if not event_names:
        raise ValidationError(
            "An endpoint with no subscriptions receives nothing. Name at least one event.",
            code="no_subscriptions",
        )

    tenant_key = setting("TENANT_SCOPE_KEY")
    if tenant_key is not None and not tenant:
        raise ValidationError(
            f"This deployment scopes events by {tenant_key!r}, so an endpoint has to name "
            f"the tenant it belongs to. One without would match no event at all.",
            code="tenant_required",
        )

    resolved_name = format_name if format_name is not None else setting("DEFAULT_FORMAT")
    if format_version is None:
        pinned = formats.latest(resolved_name)
    else:
        pinned = FormatId(name=resolved_name, version=format_version)
        formats.get(pinned)

    endpoint = Endpoint(
        name=name,
        url=url,
        secret=secret,
        format_name=pinned.name,
        format_version=pinned.version,
        tenant=tenant,
    )
    endpoint.full_clean()

    with transaction.atomic():
        endpoint.save()
        Subscription.objects.bulk_create(
            Subscription(endpoint=endpoint, event_name=name) for name in dict.fromkeys(event_names)
        )
    return endpoint
