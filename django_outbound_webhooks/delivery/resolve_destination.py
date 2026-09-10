"""Turn a hostname into an address that has been checked."""

from __future__ import annotations

import socket

import httpx2

from django_outbound_webhooks.delivery.check_address import check_address


def resolve_destination(host: str, port: int) -> str:
    """Every address this host resolves to, checked, with the first returned.

    **All of them are checked, not just the one used.** A hostname answering
    with one public address and one private one is not a misconfiguration to
    route around, it is the attack: whichever address a later resolution picks
    is the one the connection uses, and a check that looked only at the first
    would pass while the connection went elsewhere.

    A resolution failure becomes a ``ConnectError`` rather than an
    ``UnsafeDestination``. The two are opposite verdicts and the distinction is
    the whole point of separating them: DNS being briefly unavailable is the
    most ordinary transient failure there is and deserves a retry, where an
    address inside the network deserves none.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise httpx2.ConnectError(f"Could not resolve {host!r}: {exc}") from exc

    # str() is a cast rather than a guard, and the distinction matters. A
    # sockaddr's first element is typed `str | int` because the union covers
    # address families this call cannot return: with IPPROTO_TCP, getaddrinfo
    # answers only AF_INET and AF_INET6, and both carry a string there. Anything
    # that did arrive as a number would fail to parse as an address in the check
    # below, loudly, rather than being let through.
    addresses = [str(info[4][0]) for info in infos]
    for address in addresses:
        check_address(address)

    # The first, rather than a preference between families. Whatever the
    # resolver put first is what an ordinary client would have used, and every
    # candidate has already been checked, so there is nothing left to choose on.
    return addresses[0]
