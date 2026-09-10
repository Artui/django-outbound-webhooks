"""The client one delivery is sent with."""

from __future__ import annotations

from django_outbound_webhooks.delivery.webhook_client import webhook_client


def test_it_is_configured_for_posting_to_a_stranger() -> None:
    with webhook_client() as client:
        assert client.timeout.connect == 10.0
        assert client.follow_redirects is True
        assert client.max_redirects == 2
        assert client.headers["user-agent"] == "django-outbound-webhooks"


def test_redirects_are_capped_rather_than_unlimited() -> None:
    # Following a chain is how a delivery ends up at a host nobody registered,
    # which is the request-forgery hole reached the long way round.
    with webhook_client() as client:
        assert client.max_redirects < 5
