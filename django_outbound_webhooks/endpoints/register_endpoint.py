"""Create one customer endpoint, validated and pinned."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction

from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.types.format_id import FormatId

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


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
    """The supported way to add an endpoint, and the door the rules live behind.

    The model is a row: it declares two field validators and nothing else, so
    everything cross-field or policy-shaped is here, where it can be read in one
    place and tested without a database round trip per rule.

    **The version is pinned here, and recorded.** Leaving ``format_version``
    unset does not mean "follow the latest"; it means "pin whatever is latest
    right now and write that number down". An endpoint whose version is implicit
    is the unnamed-default problem one level down, and the whole reason a format
    version exists is that a consumer integrated against particular bytes.

    An explicitly requested version is checked against what is published, so a
    typo fails at registration rather than at the first delivery.
    """
    # Imported here, not at module level: Django imports an app's package before
    # the app registry is ready and this package's __init__ re-exports this
    # function, so a top-level model import would make importing the package
    # raise AppRegistryNotReady.
    from django_outbound_webhooks.models.endpoint import Endpoint
    from django_outbound_webhooks.models.subscription import Subscription

    if not event_names:
        raise ValidationError(
            "An endpoint with no subscriptions receives nothing. Name at least one event.",
            code="no_subscriptions",
        )

    tenant_key = setting("TENANT_SCOPE_KEY")
    if tenant_key is not None and not tenant:
        # Ergonomic rather than protective, and worth being clear about which.
        # An endpoint with no tenant already receives nothing under tenancy,
        # because matching filters on a non-blank value and a blank column can
        # never equal one. So this does not close a hole; it stops an operator
        # creating a row that silently never fires.
        raise ValidationError(
            f"This deployment scopes events by {tenant_key!r}, so an endpoint has to name "
            f"the tenant it belongs to. One without would match no event at all.",
            code="tenant_required",
        )

    resolved_name = format_name if format_name is not None else setting("DEFAULT_FORMAT")
    if format_version is None:
        # LookupError from an unknown family, which names the families that do
        # exist. Deliberately not caught and reworded: the registry's message is
        # already the better one.
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
