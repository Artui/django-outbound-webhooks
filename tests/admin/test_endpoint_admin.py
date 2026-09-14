"""The registry page: what it shows, what it refuses to show, and reactivation."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from django_outbound_webhooks.models.endpoint import Endpoint

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:django_outbound_webhooks_endpoint_changelist")


def test_it_is_registered_by_autodiscovery() -> None:
    # Through the site registry rather than by importing the class: what is
    # under test is that Django's autodiscovery imported the admin package at
    # all, which a direct import would paper over.
    assert Endpoint in site._registry


def test_no_secret_reaches_the_page(
    client: Client, staff_user: Callable[..., User], endpoint: Endpoint
) -> None:
    # The credential that authenticates every delivery to this customer. A
    # read-only field would still be rendered, so both columns are excluded from
    # the form rather than made read-only.
    client.force_login(staff_user("view_endpoint", "change_endpoint"))
    page = client.get(reverse("admin:django_outbound_webhooks_endpoint_change", args=[endpoint.pk]))

    body = page.content.decode()
    assert page.status_code == 200
    assert endpoint.secret not in body
    # The field, not the substring: `previous_secret_expires_at` is on the page
    # on purpose, because whether a rotation is still overlapping is exactly
    # what an operator comes here to find out, and an expiry is not a secret.
    assert 'name="secret"' not in body
    assert 'name="previous_secret"' not in body
    assert "previous_secret_expires_at" in body


def test_the_health_column_names_the_tier(endpoint: Endpoint) -> None:
    # "20" alone is meaningless: twenty dead deliveries is a rotted endpoint,
    # twenty failed requests is a bad minute.
    endpoint_admin = site._registry[Endpoint]
    endpoint.consecutive_dead_deliveries = 3
    assert "dead deliveries" in endpoint_admin.health(endpoint)


def test_the_health_column_distinguishes_the_three_states(endpoint: Endpoint) -> None:
    endpoint_admin = site._registry[Endpoint]
    assert endpoint_admin.health(endpoint) == "ok"

    endpoint.consecutive_dead_deliveries = 2
    assert "2 dead deliveries" in endpoint_admin.health(endpoint)

    endpoint.disabled_at = timezone.now()
    # Disabled wins over the count: an operator reading this row needs to know
    # the deliveries have stopped before they need to know why.
    assert endpoint_admin.health(endpoint).startswith("disabled")


def test_the_pinned_format_is_shown_the_way_it_is_written(endpoint: Endpoint) -> None:
    assert site._registry[Endpoint].pinned(endpoint) == "envelope@1"


def test_the_log_link_filters_to_this_endpoint(endpoint: Endpoint) -> None:
    # A link rather than a count: a count is a query per row, and the next
    # question is what the last attempt said, which a number cannot answer.
    link = site._registry[Endpoint].deliveries(endpoint)
    assert f"endpoint__id__exact={endpoint.pk}" in link


def test_endpoints_cannot_be_added_through_the_form(
    client: Client, staff_user: Callable[..., User]
) -> None:
    # register_endpoint is where the cross-field rules and the format pinning
    # live. A row created through a form would have no subscriptions, no
    # validated pinning, and a secret typed into a browser.
    client.force_login(staff_user("add_endpoint", "view_endpoint", "change_endpoint"))
    assert client.get(reverse("admin:django_outbound_webhooks_endpoint_add")).status_code == 403


def test_reactivate_clears_the_count_with_the_flag(
    client: Client, staff_user: Callable[..., User], endpoint: Endpoint
) -> None:
    Endpoint.objects.filter(pk=endpoint.pk).update(
        is_active=False, disabled_at=timezone.now(), consecutive_dead_deliveries=9
    )
    client.force_login(staff_user("view_endpoint", "change_endpoint"))

    response = client.post(
        CHANGELIST, {"action": "reactivate", "_selected_action": [str(endpoint.pk)]}, follow=True
    )

    assert response.status_code == 200
    endpoint.refresh_from_db()
    # All three, because re-enabling without clearing the count is an endpoint
    # that switches itself off again on its next dead delivery.
    assert (endpoint.is_active, endpoint.disabled_at, endpoint.consecutive_dead_deliveries) == (
        True,
        None,
        0,
    )
