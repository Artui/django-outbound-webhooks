"""Refusing a signing secret the specification's library would silently mangle."""

from __future__ import annotations

import base64

import pytest
from django.core.exceptions import ValidationError
from standardwebhooks import Webhook

from django_outbound_webhooks.validate_signing_secret import validate_signing_secret

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()


@pytest.mark.parametrize("secret", [SECRET, f"whsec_{SECRET}", SECRET.rstrip("=")])
def test_every_spelling_the_library_accepts_is_accepted(secret: str) -> None:
    # The check must never be stricter than the library on a working secret, or
    # it refuses registrations that would have delivered fine.
    Webhook(secret)
    validate_signing_secret(secret)


def test_the_one_the_library_accepts_and_should_not() -> None:
    # The reason this validator exists. The library decodes with
    # validate=False, so the space is discarded and "abcd" decodes to three
    # arbitrary bytes. It signs happily; only the customer's verification
    # fails, on their side, with no signal on ours.
    mangled = "ab cd"
    Webhook(mangled)  # accepted upstream, which is the whole problem
    with pytest.raises(ValidationError) as raised:
        validate_signing_secret(mangled)
    assert raised.value.code == "not_base64"


@pytest.mark.parametrize("secret", ["", "whsec_", "====", "not base64!!", "A"])
def test_a_secret_that_cannot_produce_bytes_is_refused(secret: str) -> None:
    with pytest.raises(ValidationError, match="has to be base64"):
        validate_signing_secret(secret)


def test_an_already_padded_secret_is_not_refused_as_excess_data() -> None:
    # The trap in writing this check the obvious way. The library appends "=="
    # unconditionally; doing that here with validate=True fails on a correctly
    # padded secret as excess data, so the check would refuse every ordinary
    # secret while looking strict and correct.
    assert SECRET.endswith("=")
    validate_signing_secret(SECRET)
