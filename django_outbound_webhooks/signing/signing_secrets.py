from __future__ import annotations

from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint


def signing_secrets(endpoint: Endpoint) -> list[str]:
    """The secrets to sign with, newest first."""
    secrets = [endpoint.secret]
    expires_at = endpoint.previous_secret_expires_at
    if endpoint.previous_secret and expires_at is not None and expires_at > timezone.now():
        secrets.append(endpoint.previous_secret)
    return secrets
