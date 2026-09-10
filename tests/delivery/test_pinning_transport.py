"""Connecting to the address that was checked, and no other."""

from __future__ import annotations

import httpx2
import pytest

from django_outbound_webhooks.delivery.pinning_transport import PinningTransport
from django_outbound_webhooks.delivery.unsafe_destination import UnsafeDestination


class _Recorder(httpx2.BaseTransport):
    """Stands in for the real transport and records what it was handed."""

    def __init__(self) -> None:
        self.seen: list[httpx2.Request] = []
        self.closed = False

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.seen.append(request)
        return httpx2.Response(200)

    def close(self) -> None:
        self.closed = True


def _send(url: str, monkeypatch: pytest.MonkeyPatch, resolves_to: list[str]) -> _Recorder:
    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", (address, port)) for address in resolves_to],
    )
    inner = _Recorder()
    PinningTransport(inner).handle_request(httpx2.Request("POST", url, content=b"{}"))
    return inner


def test_the_connection_goes_to_the_address_not_the_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _send("https://example.test/hooks", monkeypatch, ["93.184.216.34"])
    assert str(inner.seen[0].url) == "https://93.184.216.34/hooks"


def test_tls_still_validates_against_the_customers_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The connection layer takes server_hostname from this extension, so the
    # handshake and the certificate check use the real name even though the
    # socket goes to the pinned address. Without it, pinning would break TLS.
    inner = _send("https://example.test/hooks", monkeypatch, ["93.184.216.34"])
    assert inner.seen[0].extensions["sni_hostname"] == "example.test"


def test_the_host_header_still_names_the_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # httpx builds it at construction, before this runs, so nothing has to be
    # done to it. Asserted anyway: a virtual host served by the address would
    # answer the wrong site if this ever changed.
    inner = _send("https://example.test/hooks", monkeypatch, ["93.184.216.34"])
    assert inner.seen[0].headers["host"] == "example.test"


def test_every_resolved_address_is_checked_not_only_the_one_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The attack, rather than a misconfiguration to route around. A hostname
    # answering with one public address and one private one would pass a check
    # that looked only at the first, while a later resolution picked the other.
    with pytest.raises(UnsafeDestination, match="private"):
        _send("https://example.test/hooks", monkeypatch, ["93.184.216.34", "10.0.0.1"])


def test_a_hostname_resolving_somewhere_unsafe_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(UnsafeDestination, match="link-local"):
        _send("https://metadata.test/hooks", monkeypatch, ["169.254.169.254"])


def test_a_literal_address_is_checked_without_resolving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("a literal address has nothing to resolve")

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo", explode
    )
    inner = _Recorder()
    PinningTransport(inner).handle_request(httpx2.Request("POST", "https://93.184.216.34/hooks"))
    assert str(inner.seen[0].url) == "https://93.184.216.34/hooks"
    assert "sni_hostname" not in inner.seen[0].extensions


def test_a_literal_private_address_is_still_refused() -> None:
    with pytest.raises(UnsafeDestination, match="private"):
        PinningTransport(_Recorder()).handle_request(
            httpx2.Request("POST", "http://10.0.0.1/hooks")
        )


def test_a_resolution_failure_is_retryable_rather_than_unsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Opposite verdicts, and the distinction is the point of separating them:
    # DNS briefly unavailable deserves a retry, an address inside the network
    # deserves none.
    import socket

    def fail(*args: object, **kwargs: object) -> None:
        raise socket.gaierror("nope")

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo", fail
    )
    with pytest.raises(httpx2.ConnectError, match="Could not resolve"):
        PinningTransport(_Recorder()).handle_request(
            httpx2.Request("POST", "https://example.test/hooks")
        )


def test_closing_closes_what_it_wraps() -> None:
    inner = _Recorder()
    PinningTransport(inner).close()
    assert inner.closed


@pytest.mark.parametrize(
    ("url", "expected_port"), [("https://example.test/x", 443), ("http://example.test/x", 80)]
)
def test_the_default_port_follows_the_scheme(
    url: str, expected_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []

    def record(host: str, port: int, **kwargs: object) -> list[object]:
        seen.append(port)
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo", record
    )
    PinningTransport(_Recorder()).handle_request(httpx2.Request("POST", url))
    assert seen == [expected_port]
