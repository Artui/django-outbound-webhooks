"""Reading an endpoint's two format columns back as one identity."""

from __future__ import annotations

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.pinned_format import pinned_format
from django_outbound_webhooks.types.format_id import FormatId


def test_it_pairs_the_name_and_the_version() -> None:
    # No database: the function reads fields off an unsaved instance, which is
    # the point of it being a function rather than a method that grows.
    endpoint = Endpoint(format_name="envelope", format_version=2)
    assert pinned_format(endpoint) == FormatId(name="envelope", version=2)
