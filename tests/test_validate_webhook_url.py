"""Refusing a destination that is not an HTTP URL."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from django_outbound_webhooks.validate_webhook_url import validate_webhook_url


@pytest.mark.parametrize("url", ["https://example.test/hooks", "http://example.test:8080/x?y=1"])
def test_http_and_https_are_accepted(url: str) -> None:
    validate_webhook_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test/x",
        "file:///etc/passwd",
        "/relative/path",
        "gopher://example.test",
        "HTTPS_but_not_a_scheme",
    ],
)
def test_anything_else_is_refused(url: str) -> None:
    with pytest.raises(ValidationError) as raised:
        validate_webhook_url(url)
    assert raised.value.code == "invalid_scheme"


def test_the_scheme_check_is_case_insensitive() -> None:
    # A customer pasting HTTPS:// should not be refused for shouting.
    validate_webhook_url("HTTPS://example.test/hooks")
