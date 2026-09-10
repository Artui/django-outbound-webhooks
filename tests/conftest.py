"""Fixtures shared by the suite."""

from __future__ import annotations

from collections.abc import Iterator

import httpx2
import pytest


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[httpx2.Request]]:
    """Never let the suite post to the internet, and record what it would have.

    Autouse rather than opt-in, because the failure mode of forgetting is a test
    run that hangs on a ten-second timeout per attempt and, worse, one that
    reaches a real host if a URL in a fixture ever happens to resolve.

    Yields the requests that were made, so a test can assert on the wire without
    building its own transport.
    """
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200)

    def factory() -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(handler))

    monkeypatch.setattr("django_outbound_webhooks.delivery.deliver_due.webhook_client", factory)
    yield seen


@pytest.fixture
def second_format() -> Iterator[object]:
    """A second published format, so a test can tell a read from a default.

    Several assertions here are about *which* format an endpoint is pinned to,
    and with only one published every one of them passes against a hardcoded
    literal. Registering a second is what gives those tests something to
    distinguish.
    """
    from django_outbound_webhooks.formats.format_registry import formats
    from django_outbound_webhooks.types.format_id import FormatId
    from django_outbound_webhooks.types.rendered_body import RenderedBody

    class _Terse:
        name = "terse"
        version = 3

        def render(self, **kwargs: object) -> RenderedBody:
            return RenderedBody(body=b'{"terse":true}', content_type="application/json")

    formats.register(_Terse())
    identity = FormatId(name="terse", version=3)
    try:
        yield identity
    finally:
        formats._formats.pop(identity, None)
