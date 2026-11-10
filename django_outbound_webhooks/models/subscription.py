from __future__ import annotations

from django.db import models


class Subscription(models.Model):
    """The link between an endpoint and one event name."""

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
        # Costs a query unless the listing uses select_related("endpoint").
        return f"{self.event_name} -> {self.endpoint.name}"
