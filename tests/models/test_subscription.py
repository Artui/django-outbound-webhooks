"""One event type an endpoint has asked for."""

from __future__ import annotations

import base64

import pytest
from django.db import IntegrityError

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.subscription import Subscription

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


@pytest.fixture
def endpoint() -> Endpoint:
    return Endpoint.objects.create(
        url="https://example.test/hooks",
        secret=SECRET,
        format_name="envelope",
        format_version=1,
    )


def test_an_endpoint_can_subscribe_to_several_events(endpoint: Endpoint) -> None:
    Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderPlaced")
    Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderShipped")
    assert endpoint.subscriptions.count() == 2


def test_subscribing_twice_to_one_event_is_refused(endpoint: Endpoint) -> None:
    # Without the constraint an endpoint with a duplicated subscription would
    # be joined twice by the matching query and receive the event twice.
    Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderPlaced")
    with pytest.raises(IntegrityError):
        Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderPlaced")


def test_deleting_an_endpoint_takes_its_subscriptions(endpoint: Endpoint) -> None:
    Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderPlaced")
    endpoint.delete()
    assert Subscription.objects.count() == 0


def test_str_names_the_event_and_the_endpoint(endpoint: Endpoint) -> None:
    subscription = Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderPlaced")
    assert str(subscription) == f"shop.OrderPlaced -> {endpoint.pk}"
