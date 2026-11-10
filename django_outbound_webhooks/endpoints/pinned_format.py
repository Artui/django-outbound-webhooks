from __future__ import annotations

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.types.format_id import FormatId


def pinned_format(endpoint: Endpoint) -> FormatId:
    """Read the two columns back as one identity."""
    return FormatId(name=endpoint.format_name, version=endpoint.format_version)
