"""Fixtures for driving the admin as a real user would."""

from __future__ import annotations

import base64
from collections.abc import Callable

import pytest
from django.contrib.auth.models import Permission, User
from django.db import transaction
from django_domain_events import drain_outbox, fire

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()


@pytest.fixture
def staff_user() -> Callable[..., User]:
    """A staff user holding exactly the permissions a test names.

    Built per test rather than as a superuser, because every question worth
    asking here is about which permission was held: a superuser passes every
    check and would make the action-permission tests agree with the bug.
    """

    def make(*codenames: str, username: str = "operator") -> User:
        user = User.objects.create_user(username=username, password="x", is_staff=True)
        for codename in codenames:
            user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label="django_outbound_webhooks"
                )
            )
        return user

    return make


@pytest.fixture
def endpoint() -> Endpoint:
    return register_endpoint(
        name="Acme production",
        url="https://example.test/hooks",
        secret=SECRET,
        event_names=["testapp.OrderPlaced"],
    )


@pytest.fixture
def logged_delivery(endpoint: Endpoint) -> DeliveryAttempt:
    """One delivered webhook, with the log row it left behind."""
    with transaction.atomic():
        fire(OrderPlaced(order_id=7, total_cents=2500))
    drain_outbox()
    drain_outbox()
    return DeliveryAttempt.objects.get()
