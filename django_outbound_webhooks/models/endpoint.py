"""One customer-registered destination for webhook deliveries."""

from __future__ import annotations

from django.db import models

from django_outbound_webhooks.validate_signing_secret import validate_signing_secret
from django_outbound_webhooks.validate_webhook_url import validate_webhook_url


class Endpoint(models.Model):
    """Where one customer wants deliveries, in the shape they integrated against.

    A row and nothing else. What the columns mean lives beside the code that
    acts on them -- ``pinned_format``, ``signing_secrets``, ``endpoints_for`` --
    and the supported way to create one is ``register_endpoint``, which is where
    the cross-field rules and the format pinning live.

    The validators below are declarations rather than logic, and they are on the
    fields so that every path that runs ``full_clean`` gets them: a form, the
    admin, a serializer, and ``register_endpoint``.
    """

    url = models.URLField(max_length=2000, validators=[validate_webhook_url])
    secret = models.CharField(
        max_length=255,
        validators=[validate_signing_secret],
        help_text="Base64, optionally with the whsec_ prefix the specification uses.",
    )

    #: Pinned at registration and then frozen. The endpoint stops following the
    #: latest version the moment it is created, because the bytes it receives
    #: are what its owner wrote code against.
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    #: The customer this endpoint belongs to, matched against the event's scope.
    #: Blank only where the deployment has no tenancy at all; see
    #: ``TENANT_SCOPE_KEY``.
    tenant = models.CharField(max_length=255, blank=True, db_index=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "tenant"])]

    def __str__(self) -> str:
        return f"{self.url} ({self.format_name}@{self.format_version})"
