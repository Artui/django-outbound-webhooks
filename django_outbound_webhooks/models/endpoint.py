from __future__ import annotations

from django.db import models

from django_outbound_webhooks.endpoints.validate_webhook_url import validate_webhook_url
from django_outbound_webhooks.signing.validate_signing_secret import validate_signing_secret


class Endpoint(models.Model):
    """Where one customer wants deliveries, in the shape they integrated against."""

    #: What the customer calls this endpoint.
    name = models.CharField(max_length=100)

    url = models.URLField(max_length=2000, validators=[validate_webhook_url])
    secret = models.CharField(
        max_length=255,
        validators=[validate_signing_secret],
        help_text="Base64, optionally with the whsec_ prefix the specification uses.",
    )

    #: Pinned at registration and then frozen.
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    tenant = models.CharField(max_length=255, blank=True, db_index=True)

    previous_secret = models.CharField(max_length=255, blank=True)
    previous_secret_expires_at = models.DateTimeField(null=True, blank=True)

    consecutive_dead_deliveries = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    disabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "tenant"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"
