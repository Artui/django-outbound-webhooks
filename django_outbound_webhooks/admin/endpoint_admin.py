"""Browsing the customer-owned registry, and putting an endpoint back."""

from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timesince import timesince

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.reactivate_endpoint import reactivate_endpoint


@admin.register(Endpoint)
class EndpointAdmin(admin.ModelAdmin):
    """One customer's destinations, with health and no secrets.

    **No secret is displayed, ever.** Both secret columns are excluded from the
    form rather than made read-only, because a read-only field is still rendered:
    an operator with view access to this page would be reading the credential
    that authenticates every delivery to that customer, and a support screenshot
    would carry it out of the building. Rotation is a library call for the same
    reason -- handing the new secret back to whoever asked is a flow this page
    cannot do safely, and `rotate_secret` leaves the caller holding it.

    **Adding is off.** ``register_endpoint`` is where the cross-field rules and
    the format pinning live: a row created through a form would have no
    subscriptions, no validated pinning and a secret typed into a browser.

    Three fields are read-only for one reason each, and none of them is
    tidiness. ``tenant`` is the isolation boundary, so editing it in a form
    moves one customer's endpoint to another customer. ``format_name`` and
    ``format_version`` are the shape its owner wrote code against. The health
    columns are written by the delivery path and mean nothing if hand-edited.
    """

    list_display = ("name", "url", "tenant", "pinned", "is_active", "health", "deliveries")
    list_filter = ("is_active", "format_name")
    search_fields = ("name", "url", "tenant")
    ordering = ("-pk",)
    actions = ("reactivate",)
    exclude = ("secret", "previous_secret")
    readonly_fields = (
        "tenant",
        "format_name",
        "format_version",
        "previous_secret_expires_at",
        "consecutive_dead_deliveries",
        "disabled_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="format")
    def pinned(self, obj: Endpoint) -> str:
        return f"{obj.format_name}@{obj.format_version}"

    @admin.display(description="health")
    def health(self, obj: Endpoint) -> str:
        """What an operator is actually looking for on this page.

        Names the tier, because the number is meaningless without it: twenty
        dead *deliveries* is an endpoint that is gone, and twenty failed
        requests is a bad minute.
        """
        if obj.disabled_at is not None:
            return f"disabled {timesince(obj.disabled_at)} ago"
        if obj.consecutive_dead_deliveries:
            return f"{obj.consecutive_dead_deliveries} dead deliveries in a row"
        return "ok"

    @admin.display(description="log")
    def deliveries(self, obj: Endpoint) -> Any:
        """A link rather than a count.

        A count is a query per row on a page that renders a hundred of them, and
        the question an operator has next is "what did the last one say", which
        a number cannot answer and this link can.
        """
        url = reverse("admin:django_outbound_webhooks_deliveryattempt_changelist")
        return format_html('<a href="{}?endpoint__id__exact={}">attempts</a>', url, obj.pk)

    # `permissions=["change"]` resolves to this ModelAdmin's own
    # has_change_permission, which is Django's default here and asks for the
    # endpoint's change permission. No helper needed: the model whose rows the
    # action mutates is the model the action is listed under. The log's replay
    # action is the case where those differ.
    @admin.action(description="Reactivate selected endpoints", permissions=["change"])
    def reactivate(self, request: HttpRequest, queryset: QuerySet[Endpoint]) -> None:
        # Through reactivate_endpoint rather than queryset.update(is_active=True):
        # it clears the dead-delivery count with the flag, and an endpoint
        # re-enabled at the threshold is switched off again by its very next
        # dead delivery, which reads as this action having silently failed.
        for endpoint in queryset:
            reactivate_endpoint(endpoint)
        self.message_user(request, f"Reactivated {len(queryset)} endpoints.", messages.SUCCESS)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
