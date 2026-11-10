from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.rotate_secret import rotate_secret
from django_outbound_webhooks.signing.signing_secrets import signing_secrets

OLD = base64.b64encode(b"the-secret-it-was-registered-with").decode()
NEW = base64.b64encode(b"the-secret-it-is-rotating-to").decode()

pytestmark = pytest.mark.django_db


def _endpoint() -> Endpoint:
    return Endpoint.objects.create(
        name="Acme production",
        url="https://example.test/hooks",
        secret=OLD,
        format_name="envelope",
        format_version=1,
    )


def test_both_secrets_sign_while_the_window_is_open() -> None:
    # The entire point.
    endpoint = rotate_secret(_endpoint(), new_secret=NEW)
    assert signing_secrets(endpoint) == [NEW, OLD]


def test_the_new_secret_is_offered_first() -> None:
    endpoint = rotate_secret(_endpoint(), new_secret=NEW)
    assert signing_secrets(endpoint)[0] == NEW


def test_the_old_secret_stops_being_offered_when_the_window_closes() -> None:
    endpoint = rotate_secret(_endpoint(), new_secret=NEW, overlap_seconds=60)
    endpoint.previous_secret_expires_at = timezone.now() - timedelta(seconds=1)
    endpoint.save(update_fields=["previous_secret_expires_at"])
    assert signing_secrets(endpoint) == [NEW]


def test_a_zero_overlap_cuts_over_immediately() -> None:
    endpoint = rotate_secret(_endpoint(), new_secret=NEW, overlap_seconds=0)
    assert signing_secrets(endpoint) == [NEW]


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"SECRET_ROTATION_OVERLAP_SECONDS": 7200})
def test_the_window_defaults_to_the_configured_one() -> None:
    before = timezone.now()
    endpoint = rotate_secret(_endpoint(), new_secret=NEW)
    assert endpoint.previous_secret_expires_at is not None
    window = endpoint.previous_secret_expires_at - before
    # Bracketed from both sides.
    assert timedelta(seconds=7100) < window < timedelta(seconds=7300)


def test_a_secret_that_would_sign_with_different_bytes_is_refused() -> None:
    endpoint = _endpoint()
    with pytest.raises(ValidationError):
        rotate_secret(endpoint, new_secret="not base64!")
    assert endpoint.secret == OLD


def test_a_refused_rotation_leaves_the_instance_alone() -> None:
    endpoint = _endpoint()
    with pytest.raises(ValidationError):
        rotate_secret(endpoint, new_secret="not base64!")
    assert endpoint.previous_secret == ""
    assert endpoint.previous_secret_expires_at is None
    assert signing_secrets(endpoint) == [OLD]


def test_rotating_twice_forgets_the_oldest_secret() -> None:
    # Two columns, so the second rotation drops the first secret.
    third = base64.b64encode(b"the-third-secret-in-the-chain").decode()
    endpoint = rotate_secret(_endpoint(), new_secret=NEW)
    endpoint = rotate_secret(endpoint, new_secret=third)
    assert signing_secrets(endpoint) == [third, NEW]


def test_it_survives_a_reload() -> None:
    rotate_secret(_endpoint(), new_secret=NEW)
    assert signing_secrets(Endpoint.objects.get()) == [NEW, OLD]
