"""The format version one endpoint is pinned to."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django_outbound_webhooks.types.format_id import FormatId

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def pinned_format(endpoint: Endpoint) -> FormatId:
    """Read the two columns back as one identity.

    A function rather than a property because the row is a row: the model
    carries fields and a ``__str__``, and everything that interprets those
    fields lives beside the code that acts on the interpretation.
    """
    return FormatId(name=endpoint.format_name, version=endpoint.format_version)
