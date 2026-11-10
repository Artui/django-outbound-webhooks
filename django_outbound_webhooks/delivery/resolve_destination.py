from __future__ import annotations

import socket

import httpx2

from django_outbound_webhooks.delivery.check_address import check_address


def resolve_destination(host: str, port: int) -> str:
    """Every address this host resolves to, checked, with the first returned."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise httpx2.ConnectError(f"Could not resolve {host!r}: {exc}") from exc

    addresses = [str(info[4][0]) for info in infos]
    for address in addresses:
        check_address(address)

    return addresses[0]
