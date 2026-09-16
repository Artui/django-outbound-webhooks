"""Counting dead deliveries, and switching off an endpoint that has rotted."""

from __future__ import annotations

import base64
import logging

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.note_dead_delivery import note_dead_delivery

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


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_it_counts_towards_the_threshold_without_reaching_it() -> None:
    endpoint = _endpoint()
    assert note_dead_delivery(endpoint.pk) is False
    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 1
    assert endpoint.is_active is True


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_the_endpoint_is_disabled_on_the_threshold_and_not_before() -> None:
    # Bracketed from both sides. An assertion that it is disabled "eventually"
    # would pass for a threshold that fired one delivery early, which is a
    # customer's integration stopped sooner than the operator configured.
    endpoint = _endpoint()
    assert [note_dead_delivery(endpoint.pk) for _ in range(3)] == [False, False, True]
    endpoint.refresh_from_db()
    assert endpoint.is_active is False
    assert endpoint.disabled_at is not None


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_disabling_fires_an_event_carrying_what_survives_the_row() -> None:
    # The notification channel, and the answer to "who tells the customer".
    endpoint = _endpoint()
    for _ in range(3):
        note_dead_delivery(endpoint.pk)

    record = EventRecord.objects.get(name="django_outbound_webhooks.EndpointDisabled")
    assert record.payload["endpoint_id"] == endpoint.pk
    assert record.payload["endpoint_name"] == "Acme production"
    assert record.payload["dead_deliveries"] == 3


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_it_keeps_counting_after_the_endpoint_is_off_but_fires_once() -> None:
    # The count is what an operator reads when deciding whether re-enabling is
    # worth it, so it keeps rising. A second EndpointDisabled would be a second
    # email to a customer about something that already happened.
    endpoint = _endpoint()
    for _ in range(5):
        note_dead_delivery(endpoint.pk)

    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 5
    assert EventRecord.objects.filter(name="django_outbound_webhooks.EndpointDisabled").count() == 1


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": None})
def test_none_means_never_disable_and_still_counts() -> None:
    endpoint = _endpoint()
    for _ in range(10):
        assert note_dead_delivery(endpoint.pk) is False

    endpoint.refresh_from_db()
    assert endpoint.is_active is True
    assert endpoint.consecutive_dead_deliveries == 10
    assert not EventRecord.objects.filter(name="django_outbound_webhooks.EndpointDisabled").exists()


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 1})
def test_an_endpoint_the_customer_switched_off_is_not_disabled_again() -> None:
    # is_active is False already, so there is nothing to switch off and nobody
    # to tell. Without this the operator would get an EndpointDisabled event for
    # an endpoint they deactivated themselves.
    endpoint = _endpoint(is_active=False)
    assert note_dead_delivery(endpoint.pk) is False
    endpoint.refresh_from_db()
    assert endpoint.disabled_at is None
    assert not EventRecord.objects.filter(name="django_outbound_webhooks.EndpointDisabled").exists()


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 1})
def test_a_deleted_endpoint_is_not_an_error() -> None:
    # Deleted between the delivery and this hook. The customer removed the
    # destination; there is nothing to count and nothing owed.
    endpoint = _endpoint()
    endpoint_id = endpoint.pk
    endpoint.delete()
    assert note_dead_delivery(endpoint_id) is False


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 2})
def test_disabling_says_so_in_the_log_with_both_numbers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    endpoint = _endpoint()
    with caplog.at_level(logging.WARNING):
        note_dead_delivery(endpoint.pk)
        note_dead_delivery(endpoint.pk)

    assert "Acme production" in caplog.text
    assert "2 consecutive dead deliveries" in caplog.text


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": None})
def test_the_increment_happens_in_the_database() -> None:
    # Several deliveries to one endpoint die in parallel workers as a matter of
    # course, and that is exactly when it matters: a read, an add and a save
    # lose the increments that arrive together, which are the ones that would
    # have crossed the threshold. The claim is about concurrency and this suite
    # is single-process on SQLite, so what is asserted is the thing that makes
    # the claim true -- the database does the addition, not this process.
    endpoint = _endpoint(consecutive_dead_deliveries=4)
    with CaptureQueriesContext(connection) as queries:
        note_dead_delivery(endpoint.pk)

    updates = [q["sql"] for q in queries.captured_queries if q["sql"].startswith("UPDATE")]
    increment = next(sql for sql in updates if "+ 1" in sql)
    assert '"consecutive_dead_deliveries" + 1' in increment
    assert "= 5" not in increment
    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 5


def _failing_events() -> list[dict[str, object]]:
    return list(
        EventRecord.objects.filter(name="django_outbound_webhooks.EndpointFailing")
        .order_by("pk")
        .values_list("payload", flat=True)
    )


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_the_first_dead_delivery_warns_once_and_counts_once() -> None:
    """Once per incident, never once per delivery - and the edge that fired the
    warning is also the delivery that was counted, exactly once."""
    endpoint = _endpoint()
    assert [note_dead_delivery(endpoint.pk) for _ in range(2)] == [False, False]

    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 2
    assert _failing_events() == [
        {
            "endpoint_id": endpoint.pk,
            "endpoint_name": "Acme production",
            "disabled_after_dead_deliveries": 3,
        }
    ]


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": None})
def test_it_warns_even_when_nothing_will_switch_the_endpoint_off() -> None:
    """The configuration where the warning is the only signal anybody gets."""
    endpoint = _endpoint()
    for _ in range(3):
        assert note_dead_delivery(endpoint.pk) is False

    assert _failing_events() == [
        {
            "endpoint_id": endpoint.pk,
            "endpoint_name": "Acme production",
            "disabled_after_dead_deliveries": None,
        }
    ]


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": None})
def test_with_auto_disable_off_a_later_dead_delivery_reads_nothing() -> None:
    """The ordinary case costs two conditional updates and no read."""
    endpoint = _endpoint(consecutive_dead_deliveries=2)
    with CaptureQueriesContext(connection) as queries:
        note_dead_delivery(endpoint.pk)

    statements = [q["sql"] for q in queries.captured_queries]
    assert not [sql for sql in statements if sql.startswith("SELECT")]
    assert len([sql for sql in statements if sql.startswith("UPDATE")]) == 2


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 3})
def test_a_new_incident_after_a_reset_warns_again() -> None:
    endpoint = _endpoint()
    note_dead_delivery(endpoint.pk)
    Endpoint.objects.filter(pk=endpoint.pk).update(consecutive_dead_deliveries=0)
    note_dead_delivery(endpoint.pk)

    assert len(_failing_events()) == 2


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": 1})
def test_a_threshold_of_one_warns_and_disables_on_the_same_delivery() -> None:
    endpoint = _endpoint()
    assert note_dead_delivery(endpoint.pk) is True

    assert len(_failing_events()) == 1
    assert EventRecord.objects.filter(name="django_outbound_webhooks.EndpointDisabled").count() == 1


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"AUTO_DISABLE_AFTER_DEAD_DELIVERIES": None})
def test_the_edge_is_decided_by_the_database() -> None:
    """Exactly once only because the condition travels in the statement.

    The claim is about parallel workers and this suite is single-process, so
    what is asserted is what makes it true: the zero-to-one change is an update
    conditioned on the count being zero, not a decision made here after a read.
    """
    endpoint = _endpoint()
    with CaptureQueriesContext(connection) as queries:
        note_dead_delivery(endpoint.pk)

    first_update = next(q["sql"] for q in queries.captured_queries if q["sql"].startswith("UPDATE"))
    assert first_update.startswith(
        'UPDATE "django_outbound_webhooks_endpoint" SET "consecutive_dead_deliveries" = 1 WHERE '
    )
    condition = first_update.split(" WHERE ", 1)[1]
    assert '"consecutive_dead_deliveries" = 0' in condition


def test_a_deleted_endpoint_warns_nobody() -> None:
    endpoint = _endpoint()
    endpoint_id = endpoint.pk
    endpoint.delete()
    assert note_dead_delivery(endpoint_id) is False
    assert _failing_events() == []
