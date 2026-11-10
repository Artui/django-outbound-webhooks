from __future__ import annotations

from django.db import models


class DeliveryAttempt(models.Model):
    """A row per request, not per delivery, and the two numbers say which tier."""

    #: The stable ``webhook-id``.
    message_id = models.CharField(max_length=255, db_index=True)

    #: Nulled rather than cascaded when the customer deletes the endpoint.
    endpoint = models.ForeignKey(
        "django_outbound_webhooks.Endpoint",
        related_name="attempts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    url = models.URLField(max_length=2000)

    source_event_id = models.BigIntegerField(db_index=True)
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    outer_attempt = models.PositiveIntegerField()
    inner_attempt = models.PositiveIntegerField()

    request_body_sha256 = models.CharField(max_length=64)
    request_body_bytes = models.PositiveIntegerField()

    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error = models.TextField(blank=True)

    duration_ms = models.PositiveIntegerField()
    verdict = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("message_id", "outer_attempt", "inner_attempt")
        indexes = [models.Index(fields=["message_id", "outer_attempt", "inner_attempt"])]

    def __str__(self) -> str:
        answer = self.response_status if self.response_status is not None else "no response"
        return f"{self.message_id} {self.outer_attempt}.{self.inner_attempt} -> {answer}"
