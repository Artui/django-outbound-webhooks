from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.validate_signing_secret import validate_signing_secret


def rotate_secret(
    endpoint: Endpoint, *, new_secret: str, overlap_seconds: float | None = None
) -> Endpoint:
    """Sign with a new secret, and keep signing with the old one for a while."""
    validate_signing_secret(new_secret)

    if overlap_seconds is None:
        overlap_seconds = setting("SECRET_ROTATION_OVERLAP_SECONDS")

    endpoint.previous_secret = endpoint.secret
    endpoint.previous_secret_expires_at = timezone.now() + timedelta(seconds=overlap_seconds)
    endpoint.secret = new_secret
    endpoint.save(
        update_fields=["secret", "previous_secret", "previous_secret_expires_at", "updated_at"]
    )
    return endpoint
