"""Putting an auto-disabled endpoint back into service."""

from __future__ import annotations

import base64

import pytest
from django.test import override_settings
from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.note_dead_delivery import note_dead_delivery
from django_outbound_webhooks.operations.reactivate_endpoint import reactivate_endpoint

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _endpoint(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "format_name": "envelope",
        "format_version": 1,
    }
    fields.update(overrides)
    return Endpoint.objects.create(**fields)


def test_it_switches_the_endpoint_back_on() -> None:
    endpoint = _endpoint(is_active=False, disabled_at=timezone.now())
    reactivate_endpoint(endpoint)
    endpoint.refresh_from_db()
    assert endpoint.is_active is True
    assert endpoint.disabled_at is None


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 2})
def test_the_next_failure_does_not_disable_it_immediately() -> None:
    # The reason this function exists rather than leaving callers to set
    # is_active. An endpoint re-enabled with its count still at the threshold is
    # switched off again by its very next dead delivery, which looks exactly
    # like the re-enabling having silently failed.
    endpoint = _endpoint()
    note_dead_delivery(endpoint.pk)
    note_dead_delivery(endpoint.pk)
    endpoint.refresh_from_db()
    assert endpoint.is_active is False

    reactivate_endpoint(endpoint)
    assert note_dead_delivery(endpoint.pk) is False
    endpoint.refresh_from_db()
    assert endpoint.is_active is True


def test_reactivating_an_active_endpoint_still_clears_its_count() -> None:
    # Reasonable to want after a customer has fixed their receiver, and there is
    # nothing to refuse: the count is the thing being reset either way.
    endpoint = _endpoint(consecutive_dead_deliveries=5)
    reactivate_endpoint(endpoint)
    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 0


def test_it_survives_a_reload() -> None:
    # Writes named fields, so one left out of update_fields would pass every
    # assertion made against the in-memory instance and persist nothing.
    endpoint = _endpoint(is_active=False, disabled_at=timezone.now(), consecutive_dead_deliveries=9)
    reactivate_endpoint(endpoint)
    reloaded = Endpoint.objects.get(pk=endpoint.pk)
    assert (reloaded.is_active, reloaded.disabled_at, reloaded.consecutive_dead_deliveries) == (
        True,
        None,
        0,
    )
