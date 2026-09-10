"""Turning a hostname into a checked address."""

from __future__ import annotations

import socket

import httpx2
import pytest

from django_outbound_webhooks.delivery.resolve_destination import resolve_destination
from django_outbound_webhooks.delivery.unsafe_destination import UnsafeDestination


def _resolving(monkeypatch: pytest.MonkeyPatch, addresses: list[str]) -> None:
    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", (a, port)) for a in addresses],
    )


def test_it_returns_the_first_address(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolving(monkeypatch, ["93.184.216.34", "1.1.1.1"])
    assert resolve_destination("example.test", 443) == "93.184.216.34"


def test_one_bad_address_among_good_ones_refuses_the_lot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Whichever address a later resolution picks is the one the connection uses,
    # so a hostname that can answer with a private address is unusable even when
    # it usually answers with a public one.
    _resolving(monkeypatch, ["93.184.216.34", "127.0.0.1"])
    with pytest.raises(UnsafeDestination, match="loopback"):
        resolve_destination("example.test", 443)


def test_the_order_does_not_decide_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    # The bad one first would be caught by any implementation; the bad one last
    # is what distinguishes checking all of them from checking the one used.
    _resolving(monkeypatch, ["10.0.0.1", "93.184.216.34"])
    with pytest.raises(UnsafeDestination):
        resolve_destination("example.test", 443)


def test_a_resolution_failure_becomes_a_retryable_connect_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise socket.gaierror("temporary failure")

    monkeypatch.setattr(
        "django_outbound_webhooks.delivery.resolve_destination.socket.getaddrinfo", fail
    )
    with pytest.raises(httpx2.ConnectError, match="Could not resolve"):
        resolve_destination("example.test", 443)
