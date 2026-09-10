"""Which endpoints one event is owed to."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from django.db.models import QuerySet

from django_outbound_webhooks.settings import setting

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def endpoints_for(*, event_name: str, scope: Mapping[str, Any]) -> QuerySet[Endpoint]:
    """The active endpoints subscribed to this event, within its tenant.

    This is not routing. It is the boundary that decides whose payload reaches
    whose URL, so every branch that could widen it fails closed instead.

    With ``TENANT_SCOPE_KEY`` set, an event carrying no usable value under that
    key matches **nothing**. That is the case worth being deliberate about: an
    event fired outside a request, or by a management command, or by anything
    that forgot to open an ``attributed()`` block, arrives with an empty scope.
    Treating that as "no filter" would send it to every customer, which is the
    worst outcome this package can produce and the one that looks like a
    successful delivery from every angle.

    A blank value is treated the same as a missing one. ``tenant`` is a blank
    -able column, so a scope carrying an empty string would otherwise match
    every endpoint that never set one.
    """
    # Imported here, not at module level: Django imports an app's package
    # before the app registry is ready, and this package's __init__ re-exports
    # this function, so a top-level model import would make importing the
    # package raise AppRegistryNotReady. The substrate does the same in fire()
    # for the same reason.
    from django_outbound_webhooks.models.endpoint import Endpoint

    subscribed = Endpoint.objects.filter(is_active=True, subscriptions__event_name=event_name)

    tenant_key = setting("TENANT_SCOPE_KEY")
    if tenant_key is None:
        # No tenancy in this deployment, chosen deliberately in settings rather
        # than inferred from rows that happen to have a blank column.
        return subscribed

    value = scope.get(tenant_key)
    if value is None or value == "":
        return Endpoint.objects.none()

    # No str() here, deliberately. An event's scope is JSON and usually carries
    # an integer primary key while the column is text, so the coercion has to
    # happen -- but CharField.get_prep_value already does exactly str(), on
    # every backend, so writing it again produces a guard no test can falsify.
    # An explicit call was there and was removed once mutating it out changed
    # nothing: a line that cannot fail is a line that will be trusted for a
    # reason it does not have.
    return subscribed.filter(tenant=value)
