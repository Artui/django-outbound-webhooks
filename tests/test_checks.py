"""The system check for wiring that fails silently."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from django_domain_events import event, registry

from django_outbound_webhooks.checks import check_every_event_has_a_fan_out_receiver


def test_a_correctly_ordered_project_warns_about_nothing() -> None:
    assert check_every_event_has_a_fan_out_receiver(None) == []


def test_an_uncovered_event_is_reported_with_a_usable_hint() -> None:
    """The failure this exists for is silent: no endpoint is ever offered the
    event, a customer who subscribed sees nothing, and nothing raises.

    Declares a real event and never registers a fan-out for it, which is exactly
    the state an app loading before this package leaves behind. Reaching into
    the registry's internals to remove a receiver would test the same warning
    against a state the package cannot actually reach.
    """

    @event(name="tests.NeverFannedOut")
    @dataclass(frozen=True)
    class NeverFannedOut:
        value: int

    try:
        warnings = check_every_event_has_a_fan_out_receiver(None)
    finally:
        registry._events_by_class.pop(NeverFannedOut, None)
        registry._events_by_name.pop("tests.NeverFannedOut", None)

    assert len(warnings) == 1
    assert "tests.NeverFannedOut" in warnings[0].msg
    assert warnings[0].id == "django_outbound_webhooks.W001"
    # The hint has to name the actual rule, which is narrower than it looks:
    # only ordering against the substrate matters, because the substrate is what
    # autodiscovers every app's events.
    assert "django_domain_events" in warnings[0].hint


def test_the_registry_is_left_as_it_was_found() -> None:
    # The test above mutates process-wide state, so this is the one that would
    # notice it leaking into every later test in the session.
    assert check_every_event_has_a_fan_out_receiver(None) == []


def test_the_fan_out_event_is_never_reported_as_uncovered() -> None:
    # It has no fan-out receiver on purpose, so a check that did not exclude it
    # would warn on every correctly configured project.
    names = {entry.name for entry in registry.events()}
    assert "django_outbound_webhooks.WebhookDeliveryDue" in names
    assert check_every_event_has_a_fan_out_receiver(None) == []


def test_the_check_is_registered_with_django() -> None:
    from django.core.checks.registry import registry as check_registry

    assert check_every_event_has_a_fan_out_receiver in check_registry.get_checks()


@pytest.mark.django_db
def test_manage_py_check_passes_on_this_project() -> None:
    # The check runs where it is meant to run. A check that only ever fires from
    # a unit test is a function, not a check.
    from django.core.management import call_command

    call_command("check")
