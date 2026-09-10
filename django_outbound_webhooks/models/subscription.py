"""One event type an endpoint has asked for."""

from __future__ import annotations

from django.db import models

from django_outbound_webhooks.models.endpoint import Endpoint


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

    endpoint = models.ForeignKey(Endpoint, related_name="subscriptions", on_delete=models.CASCADE)
    #: Django creates this attribute from the foreign key above, so the checker
    #: cannot see it. Declaring it costs nothing at runtime -- a bare annotation
    #: never reaches the model metaclass -- and reading the key without it means
    #: either a query for a row we already have, or printing the wrong id.
    endpoint_id: int
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
