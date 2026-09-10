"""The bytes a format produced."""

from __future__ import annotations

import pytest

from django_outbound_webhooks.types.rendered_body import RenderedBody


def test_it_carries_bytes_and_a_content_type() -> None:
    body = RenderedBody(body=b"{}", content_type="application/json")
    assert body.body == b"{}"
    assert body.content_type == "application/json"


def test_an_empty_body_is_allowed() -> None:
    # A format is entitled to render nothing; what it is not entitled to do is
    # leave the receiver guessing how to read it.
    assert RenderedBody(body=b"", content_type="application/json").body == b""


def test_a_missing_content_type_is_refused() -> None:
    with pytest.raises(ValueError, match="content type"):
        RenderedBody(body=b"{}", content_type="")
