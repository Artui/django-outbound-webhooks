"""Change an endpoint's signing secret without a coordinated cutover."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.signing.validate_signing_secret import validate_signing_secret

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def rotate_secret(
    endpoint: Endpoint, *, new_secret: str, overlap_seconds: float | None = None
) -> Endpoint:
    """Sign with a new secret, and keep signing with the old one for a while.

    The overlap is the point. The specification carries several signatures in
    one ``webhook-signature`` header and a receiver accepts the delivery if any
    of them verifies, which is what lets the two sides move independently: this
    side rotates now, the customer deploys the new secret whenever their own
    release schedule allows, and nothing is dropped in between. Without a
    window, a rotation is a coordinated cutover with a customer who does not
    know it is happening.

    ``overlap_seconds`` defaults to ``SECRET_ROTATION_OVERLAP_SECONDS`` rather
    than to a literal, so a deployment sets its window once. Passing ``0``
    rotates with no overlap at all, which is the right thing for exactly one
    case -- a leaked secret, where continuing to accept it is the problem -- and
    the wrong thing for every other.

    The new secret is validated **before** anything on the instance changes, by
    calling the field's own validator rather than ``full_clean``. Two reasons,
    and only the first is obvious. A refused rotation must not leave the
    caller's object holding a secret that was never saved -- they are likely to
    catch the error and carry on using it. And ``full_clean`` would re-validate
    the URL, so an endpoint registered before a validator tightened could not
    rotate its secret at all: a rotation would fail for a reason that has
    nothing to do with rotating, at the moment a leak makes it urgent.
    """
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
