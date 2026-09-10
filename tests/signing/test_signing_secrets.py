"""Which secrets an endpoint's deliveries are signed with."""

from __future__ import annotations

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.signing.signing_secrets import signing_secrets


def test_one_column_today_still_answers_with_a_list() -> None:
    # The caller is written against the shape rotation needs, so adding the
    # second column changes no call site.
    assert signing_secrets(Endpoint(secret="abcd")) == ["abcd"]
