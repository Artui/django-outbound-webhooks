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
    """One customer's destinations, with health and no secrets."""

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
        """What an operator is actually looking for on this page."""
        if obj.disabled_at is not None:
            return f"disabled {timesince(obj.disabled_at)} ago"
        if obj.consecutive_dead_deliveries:
            return f"{obj.consecutive_dead_deliveries} dead deliveries in a row"
        return "ok"

    @admin.display(description="log")
    def deliveries(self, obj: Endpoint) -> Any:
        """A link rather than a count."""
        url = reverse("admin:django_outbound_webhooks_deliveryattempt_changelist")
        return format_html('<a href="{}?endpoint__id__exact={}">attempts</a>', url, obj.pk)

    # `permissions=["change"]` resolves to this ModelAdmin's has_change_permission.
    @admin.action(description="Reactivate selected endpoints", permissions=["change"])
    def reactivate(self, request: HttpRequest, queryset: QuerySet[Endpoint]) -> None:
        for endpoint in queryset:
            reactivate_endpoint(endpoint)
        self.message_user(request, f"Reactivated {len(queryset)} endpoints.", messages.SUCCESS)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
