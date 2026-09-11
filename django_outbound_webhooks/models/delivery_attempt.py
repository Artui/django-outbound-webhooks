"""One HTTP request made on one delivery's behalf."""

from __future__ import annotations

from django.db import models


class DeliveryAttempt(models.Model):
    """A row per request, not per delivery, and the two numbers say which tier.

    ``outer_attempt`` counts the substrate's deliveries of this webhook;
    ``inner_attempt`` counts the requests inside one of those. They multiply
    rather than add, so a log that called either of them "attempt" would make
    every number in it ambiguous, and an auto-disable threshold counted in one
    would silently mean the other.
    """

    #: The stable ``webhook-id``. The identity a customer deduplicates on, and
    #: therefore the one an operator searches by when a customer reports a
    #: problem.
    message_id = models.CharField(max_length=255, db_index=True)

    #: Nulled rather than cascaded when the customer deletes the endpoint. A
    #: delivery log whose rows disappear with the thing they are evidence about
    #: is not a log.
    endpoint = models.ForeignKey(
        "django_outbound_webhooks.Endpoint",
        related_name="attempts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    #: Denormalised on purpose, and not only for the null case above: an
    #: endpoint's URL can be edited, and the question this answers is where the
    #: request went, not where it would go now.
    url = models.URLField(max_length=2000)

    source_event_id = models.BigIntegerField(db_index=True)
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    outer_attempt = models.PositiveIntegerField()
    inner_attempt = models.PositiveIntegerField()

    #: The hash rather than the body. The body is the customer's data and would
    #: double this table's size, while the hash answers the question the body
    #: was kept for: whether two attempts of one delivery sent the same bytes.
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
