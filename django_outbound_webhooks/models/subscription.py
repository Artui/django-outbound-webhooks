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
        # Names the endpoint rather than its primary key, which is the useful
        # string for anyone reading a log line or a delete confirmation, and
        # incidentally needs no annotation for ty's benefit: the implicit
        # endpoint_id is invisible to a checker where the relation is not.
        #
        # It costs one query on an instance that did not fetch the endpoint, so
        # any listing that renders this needs select_related("endpoint"). The
        # admin lands in 0.4.0 and that is where the obligation falls due.
        return f"{self.event_name} -> {self.endpoint.name}"
