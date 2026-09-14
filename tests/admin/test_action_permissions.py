"""Who may run an action, which Django gets wrong by default.

The hazard both ModelAdmins here guard against: an action declared without
``permissions=`` is offered to **anyone who can reach the changelist**, which
includes view-only staff, and ``has_change_permission`` gates the form rather
than the action, so refusing there refuses nothing.

Every test drives the changelist with the test client rather than calling the
action method. Calling it directly proves nothing at all: the permission check
lives in how Django *offers* and dispatches the action, not in the method.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint

pytestmark = pytest.mark.django_db

ENDPOINTS = reverse("admin:django_outbound_webhooks_endpoint_changelist")
DELIVERIES = reverse("admin:django_outbound_webhooks_deliveryattempt_changelist")


def test_view_only_staff_are_not_offered_reactivate(
    client: Client, staff_user: Callable[..., User], endpoint: Endpoint
) -> None:
    client.force_login(staff_user("view_endpoint"))
    page = client.get(ENDPOINTS)
    assert page.status_code == 200
    assert "reactivate" not in page.content.decode()


def test_view_only_staff_cannot_run_reactivate_by_posting(
    client: Client, staff_user: Callable[..., User], endpoint: Endpoint
) -> None:
    # The half that matters. An action absent from the dropdown is still
    # reachable by anyone who can type a form post, so the refusal has to be in
    # the dispatch rather than in the rendering.
    Endpoint.objects.filter(pk=endpoint.pk).update(
        is_active=False, disabled_at=timezone.now(), consecutive_dead_deliveries=9
    )
    client.force_login(staff_user("view_endpoint"))

    client.post(
        ENDPOINTS, {"action": "reactivate", "_selected_action": [str(endpoint.pk)]}, follow=True
    )

    endpoint.refresh_from_db()
    assert endpoint.is_active is False
    assert endpoint.consecutive_dead_deliveries == 9


def test_change_permission_is_what_enables_reactivate(
    client: Client, staff_user: Callable[..., User], endpoint: Endpoint
) -> None:
    # The positive case, against the same starting state, so the test above is
    # known to be refusing rather than merely not reaching the action.
    Endpoint.objects.filter(pk=endpoint.pk).update(is_active=False)
    client.force_login(staff_user("view_endpoint", "change_endpoint"))

    client.post(
        ENDPOINTS, {"action": "reactivate", "_selected_action": [str(endpoint.pk)]}, follow=True
    )

    endpoint.refresh_from_db()
    assert endpoint.is_active is True


def test_reading_the_log_does_not_let_you_replay(
    client: Client,
    staff_user: Callable[..., User],
    logged_delivery: DeliveryAttempt,
    no_real_network: list[httpx2.Request],
) -> None:
    # Replay is gated on the *endpoint's* change permission, not this table's,
    # and this is the case that tells them apart: a support user granted every
    # permission the log has still cannot make a delivery happen.
    client.force_login(staff_user("view_deliveryattempt", "change_deliveryattempt"))

    before = len(no_real_network)
    client.post(
        DELIVERIES,
        {"action": "replay", "_selected_action": [str(logged_delivery.pk)]},
        follow=True,
    )

    assert len(no_real_network) == before


def test_endpoint_change_permission_is_what_enables_replay(
    client: Client,
    staff_user: Callable[..., User],
    logged_delivery: DeliveryAttempt,
    no_real_network: list[httpx2.Request],
) -> None:
    client.force_login(staff_user("view_deliveryattempt", "change_endpoint"))

    response = client.post(
        DELIVERIES,
        {"action": "replay", "_selected_action": [str(logged_delivery.pk)]},
        follow=True,
    )

    assert "Replayed 1 deliveries." in response.content.decode()
