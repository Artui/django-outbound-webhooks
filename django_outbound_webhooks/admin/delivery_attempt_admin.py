"""Browsing the delivery log, and replaying from it."""

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
    """The log, read-only, with replay as an action.

    Every field is read-only and nothing can be added or deleted by hand. A
    delivery log whose rows can be edited is not evidence of anything, and the
    question it exists to answer -- what did we send, where, and what came back
    -- is only worth asking of rows nobody has touched. Retention belongs to the
    substrate's pruning rather than to a delete button that would take the
    evidence and leave the deliveries.
    """

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
    # Narrowing, not enabling. Django already select_relates when list_display
    # names a foreign key -- but it calls `select_related()` with no arguments,
    # which follows every non-null relation the model has. Naming the one that
    # is rendered keeps a column added later from silently joining another
    # table on a page that lists a hundred rows. Do not write a query-count test
    # for this: it passes either way, because the automatic join is there.
    list_select_related = ("endpoint",)
    # Off because it costs a second COUNT(*) over the whole log on every page
    # load, and this is the page somebody opens during an incident.
    show_full_result_count = False

    @admin.display(description="attempt")
    def attempt(self, obj: DeliveryAttempt) -> str:
        """Both numbers, in the only notation that says which tier is which.

        ``3.2`` is the third delivery of this webhook and the second HTTP
        request inside it. They multiply rather than add, so a single "attempt"
        column would make every number on this page ambiguous.
        """
        return f"{obj.outer_attempt}.{obj.inner_attempt}"

    @admin.action(description="Replay selected deliveries", permissions=["replay"])
    def replay(self, request: HttpRequest, queryset: QuerySet[DeliveryAttempt]) -> None:
        """Send each selected delivery again, once per delivery rather than per row.

        The log holds a row per HTTP *request*, so selecting a failed delivery
        selects several rows of one delivery. Replaying per row would send the
        customer one webhook per attempt the original made -- most for a
        delivery that failed, which is exactly the selection somebody makes
        here.
        """
        message_ids = list(dict.fromkeys(queryset.values_list("message_id", flat=True)))

        sent, refused = 0, []
        for message_id in message_ids:
            try:
                replay_delivery(message_id=message_id)
            except ReplayRefused as refusal:
                # Reported rather than raised. A selection of twenty where one
                # endpoint has been deleted should replay the nineteen and say
                # what happened to the other, not abort with nothing sent.
                refused.append(str(refusal))
            else:
                sent += 1

        if sent:
            self.message_user(request, f"Replayed {sent} deliveries.", messages.SUCCESS)
        for refusal in refused:
            self.message_user(request, refusal, messages.WARNING)

    def has_replay_permission(self, request: HttpRequest) -> bool:
        """Who may replay, checked separately from who may read the log.

        Gated on the **endpoint's** change permission rather than this table's,
        and that is the interesting half. A replay mutates nothing here; what it
        does is send a customer a webhook. The permission that should govern
        that is the one governing the endpoints, so somebody granted read access
        to the log for support purposes can read it without being able to make
        deliveries happen.
        """
        return may_change(request, Endpoint._meta)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)
