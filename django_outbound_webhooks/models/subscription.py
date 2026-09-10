"""One event type an endpoint has asked for."""

from __future__ import annotations

from django.db import models


class Subscription(models.Model):
    """The link between an endpoint and one event name.

    A row per subscription rather than a list on the endpoint. Two reasons, and
    the second is the one that decided it.

    It keeps "which endpoints want this event" an indexed lookup instead of a
    scan over a JSON column, and it keeps that lookup the same statement on
    every backend rather than one that depends on how the database implements
    JSON containment.

    And it is the shape the question grows into. The incumbent's open issues ask
    for topics that are not model names and for subscriptions that can be
    narrowed, so the thing an endpoint subscribes to is going to acquire fields.
    A list of strings has nowhere to put them.
    """

    # Django adds endpoint_id at runtime. The bare annotation makes it visible
    # to ty, which never sees it -- the same fix django-domain-events uses on
    # DeliveryRecord.event_id, reached there independently.
    #
    # Two things that do not remove the need for it, both tried 2026-09-10. The
    # string reference below is right for its own reason (no model module
    # imports another) and is unrelated to this. And django-stubs cannot supply
    # it: <fk>_id is synthesised by the mypy plugin from the field's attname,
    # not declared in any stub, and this family has no mypy for the plugin to
    # run under.
    endpoint_id: int

    endpoint = models.ForeignKey(
        "django_outbound_webhooks.Endpoint",
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    event_name = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint", "event_name"],
                name="unique_subscription_per_endpoint",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_name} -> {self.endpoint_id}"
