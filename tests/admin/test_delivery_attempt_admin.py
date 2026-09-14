"""The log page: read-only, both tiers legible, and replay from a selection."""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest
from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:django_outbound_webhooks_deliveryattempt_changelist")


def test_it_is_registered_by_autodiscovery() -> None:
    assert DeliveryAttempt in site._registry


def test_the_log_cannot_be_edited(
    client: Client, staff_user: Callable[..., User], logged_delivery: DeliveryAttempt
) -> None:
    # A log whose rows can be edited is not evidence of anything. Asserted
    # through the pages rather than the flags, because that is where an operator
    # meets the refusal.
    client.force_login(staff_user("view_deliveryattempt", "change_deliveryattempt"))
    assert (
        client.get(reverse("admin:django_outbound_webhooks_deliveryattempt_add")).status_code == 403
    )
    detail = reverse(
        "admin:django_outbound_webhooks_deliveryattempt_change", args=[logged_delivery.pk]
    )
    # Django serves a read-only detail view to a user with view permission, so
    # what is asserted is that nothing on it can be submitted.
    page = client.get(detail)
    assert page.status_code == 200
    assert 'name="_save"' not in page.content.decode()


def test_the_attempt_column_says_which_tier_is_which(
    logged_delivery: DeliveryAttempt,
) -> None:
    # "3.2" is the third delivery of this webhook and the second request inside
    # it. The two multiply, so one "attempt" column would make every number on
    # the page ambiguous.
    logged_delivery.outer_attempt, logged_delivery.inner_attempt = 3, 2
    assert site._registry[DeliveryAttempt].attempt(logged_delivery) == "3.2"


def test_replay_sends_one_delivery_per_message_not_per_row(
    client: Client,
    staff_user: Callable[..., User],
    logged_delivery: DeliveryAttempt,
    no_real_network: list[httpx2.Request],
) -> None:
    # The log holds a row per HTTP request, so a failed delivery is several
    # rows. Replaying per row would send the customer one webhook per attempt
    # the original made -- and a failing delivery is exactly the selection
    # somebody makes here.
    twin = DeliveryAttempt.objects.get(pk=logged_delivery.pk)
    twin.pk = None
    twin.inner_attempt = 2
    twin.save()

    client.force_login(staff_user("view_deliveryattempt", "change_endpoint"))
    response = client.post(
        CHANGELIST,
        {"action": "replay", "_selected_action": [str(logged_delivery.pk), str(twin.pk)]},
        follow=True,
    )

    assert response.status_code == 200
    assert "Replayed 1 deliveries." in response.content.decode()


def test_a_refusal_is_reported_and_does_not_stop_the_rest(
    client: Client,
    staff_user: Callable[..., User],
    logged_delivery: DeliveryAttempt,
    no_real_network: list[httpx2.Request],
) -> None:
    # A selection of two where one endpoint has been deleted should replay the
    # one it can and say what happened to the other, rather than aborting with
    # nothing sent.
    orphan = DeliveryAttempt.objects.get(pk=logged_delivery.pk)
    orphan.pk = None
    orphan.message_id = "msg_orphaned"
    orphan.endpoint = None
    orphan.save()

    client.force_login(staff_user("view_deliveryattempt", "change_endpoint"))
    response = client.post(
        CHANGELIST,
        {"action": "replay", "_selected_action": [str(logged_delivery.pk), str(orphan.pk)]},
        follow=True,
    )

    body = response.content.decode()
    assert "Replayed 1 deliveries." in body
    assert "has been deleted" in body


def test_replaying_an_inactive_endpoint_says_so(
    client: Client,
    staff_user: Callable[..., User],
    logged_delivery: DeliveryAttempt,
    no_real_network: list[httpx2.Request],
) -> None:
    # Without the refusal the replay is fired, claimed and dropped by the
    # receiver's own guard: the operator reads "replayed" and the customer
    # receives nothing.
    Endpoint.objects.all().update(is_active=False)
    client.force_login(staff_user("view_deliveryattempt", "change_endpoint"))

    response = client.post(
        CHANGELIST,
        {"action": "replay", "_selected_action": [str(logged_delivery.pk)]},
        follow=True,
    )

    body = response.content.decode()
    assert "not active" in body
    assert "Replayed" not in body
