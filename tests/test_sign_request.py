"""Signature headers, and the two ways they silently come out wrong."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest
from standardwebhooks import Webhook, WebhookVerificationError

from django_outbound_webhooks.sign_request import sign_request

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()
OTHER_SECRET = base64.b64encode(b"the-incoming-rotation-secret!!!").decode()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def test_a_conforming_receiver_verifies_what_it_signs() -> None:
    # The only assertion that means anything about conformance: hand the bytes
    # and the headers to the specification's own verifier, which is what a
    # customer runs.
    body = b'{"hello":"world"}'
    headers = sign_request(secrets=[SECRET], message_id="msg_1", timestamp=_now(), body=body)
    assert Webhook(SECRET).verify(body, headers) == {"hello": "world"}


def test_the_three_headers_are_present_and_named_by_the_spec() -> None:
    headers = sign_request(secrets=[SECRET], message_id="msg_1", timestamp=_now(), body=b"{}")
    assert set(headers) == {"webhook-id", "webhook-timestamp", "webhook-signature"}
    assert headers["webhook-id"] == "msg_1"
    assert headers["webhook-signature"].startswith("v1,")


def test_rotation_signs_with_every_secret_at_once() -> None:
    # The overlap window, and it comes free with the format: several signatures
    # in one space-separated header, so both the outgoing and the incoming
    # secret verify with no coordinated cutover.
    body = b"{}"
    headers = sign_request(
        secrets=[SECRET, OTHER_SECRET], message_id="msg_1", timestamp=_now(), body=body
    )
    assert len(headers["webhook-signature"].split(" ")) == 2
    Webhook(SECRET).verify(body, headers)
    Webhook(OTHER_SECRET).verify(body, headers)


def test_a_secret_that_was_rotated_out_no_longer_verifies() -> None:
    # Without this the rotation test above passes even if the function signed
    # with every secret it has ever seen.
    body = b"{}"
    headers = sign_request(secrets=[SECRET], message_id="msg_1", timestamp=_now(), body=body)
    with pytest.raises(WebhookVerificationError):
        Webhook(OTHER_SECRET).verify(body, headers)


def test_an_aware_timestamp_outside_utc_is_converted_rather_than_relabelled() -> None:
    # The trap this function exists for. `Webhook.sign` calls
    # `timestamp.replace(tzinfo=utc)`, which keeps the wall clock and moves the
    # instant. Signing 14:00+02:00 as though it were 14:00Z puts the delivery
    # two hours in the future, and every receiver rejects it as too new -- a
    # signature failure carrying a correct signature.
    stockholm = timezone(timedelta(hours=2))
    instant = datetime.now(tz=stockholm)
    headers = sign_request(secrets=[SECRET], message_id="msg_1", timestamp=instant, body=b"{}")
    assert int(headers["webhook-timestamp"]) == int(instant.timestamp())
    # And the receiver agrees, which the raw comparison above cannot show.
    Webhook(SECRET).verify(b"{}", headers)


def test_the_header_timestamp_is_the_one_that_was_signed() -> None:
    # Deriving the header and the signature from two different values is how
    # they come to disagree, and the failure is total: no receiver verifies,
    # while every local test of the signer passes.
    instant = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
    headers = sign_request(secrets=[SECRET], message_id="msg_1", timestamp=instant, body=b"{}")
    expected = Webhook(SECRET).sign(msg_id="msg_1", timestamp=instant, data="{}")
    assert headers["webhook-signature"] == expected
    assert headers["webhook-timestamp"] == str(int(instant.timestamp()))


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValueError, match="aware datetime"):
        sign_request(
            secrets=[SECRET],
            message_id="msg_1",
            timestamp=datetime(2026, 9, 9, 12, 0, 0),
            body=b"{}",
        )


def test_no_secrets_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one signing secret"):
        sign_request(secrets=[], message_id="msg_1", timestamp=_now(), body=b"{}")


def test_a_body_that_is_not_utf8_is_refused_with_the_reason() -> None:
    # The specification signs `{id}.{timestamp}.{body}` as one UTF-8 string, so
    # a binary body cannot be signed to it at all. Refusing names that; letting
    # it through would mean inventing a signature format.
    with pytest.raises(ValueError, match="UTF-8 body"):
        sign_request(secrets=[SECRET], message_id="msg_1", timestamp=_now(), body=b"\xff\xfe")
