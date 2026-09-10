"""A transport that connects to the address it checked, and no other."""

from __future__ import annotations

import ipaddress

import httpx2

from django_outbound_webhooks.delivery.check_address import check_address
from django_outbound_webhooks.delivery.resolve_destination import resolve_destination


class PinningTransport(httpx2.BaseTransport):
    """Resolve, check, then connect to *that* address.

    Checking a hostname and then handing the hostname to the connection layer is
    not a defence, it is a race with a name. The attacker controls the DNS
    answer, so the resolution the check saw and the resolution the socket uses
    are two different questions, and a record with a one-second time-to-live is
    all it takes for the second to differ. This closes the gap the only way it
    closes: the address that was checked is the address that is dialled.

    TLS survives the rewrite because the connection layer takes its
    ``server_hostname`` from the ``sni_hostname`` extension when one is set, so
    the handshake and the certificate check still use the customer's real
    hostname. Verified against httpcore2's connection module rather than assumed.

    The ``Host`` header needs nothing done to it: httpx builds it when the
    request is constructed, which is before this runs, so it already names the
    hostname rather than the address.
    """

    def __init__(self, inner: httpx2.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        host = request.url.host

        if _is_literal_address(host):
            # Nothing to pin: the URL already names the address, so there is no
            # second resolution to disagree with the first.
            check_address(host)
            return self._inner.handle_request(request)

        pinned = resolve_destination(host, request.url.port or _default_port(request.url))

        request.url = request.url.copy_with(host=pinned)
        request.extensions = {**request.extensions, "sni_hostname": host}
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def _is_literal_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _default_port(url: httpx2.URL) -> int:
    return 443 if url.scheme == "https" else 80
