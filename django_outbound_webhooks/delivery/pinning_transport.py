from __future__ import annotations

import ipaddress

import httpx2

from django_outbound_webhooks.delivery.check_address import check_address
from django_outbound_webhooks.delivery.resolve_destination import resolve_destination


class PinningTransport(httpx2.BaseTransport):
    """Resolve, check, then connect to *that* address."""

    def __init__(self, inner: httpx2.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        host = request.url.host

        if _is_literal_address(host):
            # A literal address has no second resolution to disagree with the first.
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
