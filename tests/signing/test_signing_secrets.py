"""Which secrets an endpoint's deliveries are signed with."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.signing.signing_secrets import signing_secrets


def test_an_endpoint_that_has_never_rotated_signs_with_one() -> None:
    assert signing_secrets(Endpoint(secret="abcd")) == ["abcd"]


def test_an_open_window_offers_the_previous_secret_too() -> None:
    endpoint = Endpoint(
        secret="new",
        previous_secret="old",
        previous_secret_expires_at=timezone.now() + timedelta(hours=1),
    )
    assert signing_secrets(endpoint) == ["new", "old"]


def test_a_closed_window_does_not() -> None:
    endpoint = Endpoint(
        secret="new",
        previous_secret="old",
        previous_secret_expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert signing_secrets(endpoint) == ["new"]


def test_a_blank_previous_secret_is_never_signed_with() -> None:
    # An inconsistent row: an expiry standing over no secret. rotate_secret
    # cannot write one, but a column is editable by anything with a database
    # connection, and without the first half of the condition every delivery
    # would carry a second signature made with the empty string -- which the
    # customer cannot verify and nobody can explain.
    endpoint = Endpoint(
        secret="new",
        previous_secret="",
        previous_secret_expires_at=timezone.now() + timedelta(hours=1),
    )
    assert signing_secrets(endpoint) == ["new"]


def test_a_previous_secret_with_no_window_is_never_signed_with() -> None:
    # The other inconsistent row, and the other half of the condition. A secret
    # left behind with no expiry would otherwise be offered forever, which is a
    # rotation that never finishes.
    endpoint = Endpoint(secret="new", previous_secret="old", previous_secret_expires_at=None)
    assert signing_secrets(endpoint) == ["new"]
