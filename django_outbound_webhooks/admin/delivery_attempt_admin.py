from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from django_outbound_webhooks.admin.utils import may_change
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.replay_delivery import ReplayRefused, replay_delivery


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    """The log, read-only, with replay as an action."""

    list_display = (
        "message_id",
        "endpoint",
        "attempt",
        "verdict",
        "response_status",
        "duration_ms",
        "created_at",
    )
    list_filter = ("verdict", "format_name")
    search_fields = ("message_id", "url")
    ordering = ("-pk",)
    actions = ("replay",)
    # Narrowing, not enabling.
    list_select_related = ("endpoint",)
    # Off: a COUNT(*) over the whole log on every page load is too slow mid-incident.
    show_full_result_count = False

    @admin.display(description="attempt")
    def attempt(self, obj: DeliveryAttempt) -> str:
        """Both numbers, in the only notation that says which tier is which."""
        return f"{obj.outer_attempt}.{obj.inner_attempt}"

    @admin.action(description="Replay selected deliveries", permissions=["replay"])
    def replay(self, request: HttpRequest, queryset: QuerySet[DeliveryAttempt]) -> None:
        """Send each selected delivery again, once per delivery rather than per row."""
        message_ids = list(dict.fromkeys(queryset.values_list("message_id", flat=True)))

        sent, refused = 0, []
        for message_id in message_ids:
            try:
                replay_delivery(message_id=message_id)
            except ReplayRefused as refusal:
                refused.append(str(refusal))
            else:
                sent += 1

        if sent:
            self.message_user(request, f"Replayed {sent} deliveries.", messages.SUCCESS)
        for refusal in refused:
            self.message_user(request, refusal, messages.WARNING)

    def has_replay_permission(self, request: HttpRequest) -> bool:
        """Who may replay, checked separately from who may read the log."""
        return may_change(request, Endpoint._meta)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)
