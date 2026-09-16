"""Forgetting an endpoint's failures once it answers again."""

from __future__ import annotations

import base64

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django_domain_events.models.event_record import EventRecord

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.note_successful_delivery import note_successful_delivery

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


def _recovered_events() -> list[dict[str, object]]:
    return list(
        EventRecord.objects.filter(name="django_outbound_webhooks.EndpointRecovered")
        .order_by("pk")
        .values_list("payload", flat=True)
    )


def test_a_success_clears_what_came_before_it() -> None:
    # "Sustained" is the whole content of auto-disable. Without this, the
    # threshold counts lifetime failures and every endpoint reaches it in the
    # end, including one that has never had a bad week.
    endpoint = _endpoint(consecutive_dead_deliveries=7)
    note_successful_delivery(endpoint)
    endpoint.refresh_from_db()
    assert endpoint.consecutive_dead_deliveries == 0


def test_it_does_not_re_enable_an_endpoint() -> None:
    # A disabled endpoint delivers nothing, so this cannot be reached through
    # the delivery path -- but a replay or a hand-fired delivery could, and
    # "the endpoint answered once" is not the same decision as "put it back into
    # service", which is reactivate_endpoint and is somebody's choice.
    endpoint = _endpoint(consecutive_dead_deliveries=20, is_active=False)
    note_successful_delivery(endpoint)
    endpoint.refresh_from_db()
    assert endpoint.is_active is False


def test_the_ordinary_case_is_one_statement_that_touches_no_row() -> None:
    # Every successful delivery runs this, and almost every endpoint is already
    # at zero. The filter is what keeps that from rewriting a row per delivery.
    #
    # It is *not* free, and this test is what established that: Django sends the
    # UPDATE with the condition in its WHERE clause rather than deciding here,
    # so the statement is issued and matches nothing. The claim that it cost no
    # write at all was in this module's docstring until this assertion was
    # written, which is the usual way round.
    endpoint = _endpoint()
    with CaptureQueriesContext(connection) as queries:
        note_successful_delivery(endpoint)

    assert len(queries.captured_queries) == 1
    # The condition travels in the statement, which is what keeps the row
    # untouched. Asserting the column is zero afterwards would pass just as
    # happily for an unconditional write, since it was already zero.
    assert '"consecutive_dead_deliveries" > 0' in queries.captured_queries[0]["sql"]
    assert Endpoint.objects.filter(pk=endpoint.pk, consecutive_dead_deliveries=0).exists()


def test_a_missing_endpoint_is_not_an_error() -> None:
    endpoint = _endpoint(consecutive_dead_deliveries=3)
    Endpoint.objects.filter(pk=endpoint.pk).delete()
    note_successful_delivery(endpoint)
    assert _recovered_events() == []


def test_the_success_that_ends_an_incident_says_so_once() -> None:
    """The reset, and only the reset: the second success finds nothing to
    clear and is not an event."""
    endpoint = _endpoint(consecutive_dead_deliveries=4)
    with transaction.atomic():
        note_successful_delivery(endpoint)
        note_successful_delivery(endpoint)

    assert _recovered_events() == [{"endpoint_id": endpoint.pk, "endpoint_name": "Acme production"}]


def test_an_endpoint_that_was_not_failing_is_not_recovered() -> None:
    endpoint = _endpoint()
    note_successful_delivery(endpoint)
    assert _recovered_events() == []


def test_recovering_costs_no_read() -> None:
    """The event rides on the update's answer, and the name comes from the
    endpoint the delivery already loaded to send the request."""
    endpoint = _endpoint(consecutive_dead_deliveries=4)
    with CaptureQueriesContext(connection) as queries, transaction.atomic():
        note_successful_delivery(endpoint)

    statements = [q["sql"] for q in queries.captured_queries]
    assert not [sql for sql in statements if sql.startswith("SELECT")]
    assert len(_recovered_events()) == 1
