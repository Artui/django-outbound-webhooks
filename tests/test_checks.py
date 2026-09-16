"""The system check for wiring that fails silently."""

from __future__ import annotations

import pytest
from django.test import override_settings

from django_outbound_webhooks.checks import check_default_format_is_published


@pytest.mark.django_db
def test_manage_py_check_passes_on_this_project() -> None:
    # The check runs where it is meant to run. A check that only ever fires from
    # a unit test is a function, not a check.
    from django.core.management import call_command

    call_command("check")


def test_a_default_naming_a_published_family_warns_about_nothing() -> None:
    assert check_default_format_is_published(None) == []


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"DEFAULT_FORMAT": "cloudevents"})
def test_a_default_naming_the_conditional_family_is_fine_once_it_is_published() -> None:
    # The suite configures a CloudEvents source, so this is the good case of
    # the exact value the bad case uses. Without it, the warning below would be
    # indistinguishable from "this check dislikes cloudevents".
    assert check_default_format_is_published(None) == []


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"DEFAULT_FORMAT": "nothing-publishes-this"})
def test_a_default_that_no_format_publishes_is_reported_with_the_likely_cause() -> None:
    # The failure being guarded: nothing raises at startup, and the first
    # customer to register an endpoint gets the LookupError instead.
    warnings = check_default_format_is_published(None)

    assert len(warnings) == 1
    assert warnings[0].id == "django_outbound_webhooks.W002"
    assert "nothing-publishes-this" in warnings[0].msg
    # Naming what does exist is half the value: the likeliest mistake is a
    # family that is spelled correctly and not published.
    assert "envelope" in warnings[0].msg
    assert "CLOUDEVENTS_SOURCE" in warnings[0].hint


def test_the_format_check_is_registered_with_django() -> None:
    from django.core.checks.registry import registry as check_registry

    assert check_default_format_is_published in check_registry.get_checks()
