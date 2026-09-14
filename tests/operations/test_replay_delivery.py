"""Replaying a logged delivery, and the four things that stop one."""

from __future__ import annotations

import base64

import httpx2
import pytest
from django.db import transaction
from django_domain_events import drain_outbox, fire
from django_domain_events.models.event_record import EventRecord
from standardwebhooks import Webhook

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.delivery_attempt import DeliveryAttempt
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.operations.replay_delivery import ReplayRefused, replay_delivery
from django_outbound_webhooks.operations.rotate_secret import rotate_secret
from tests.testapp.events import OrderPlaced

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _endpoint(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "event_names": ["testapp.OrderPlaced"],
    }
    fields.update(overrides)
    return register_endpoint(**fields)


def _deliver_once() -> tuple[Endpoint, str]:
    """Fan out and deliver one event, and return the endpoint and message id."""
    endpoint = _endpoint()
    with transaction.atomic():
        fire(OrderPlaced(order_id=7, total_cents=2500))
    drain_outbox()
    drain_outbox()
    attempt = DeliveryAttempt.objects.get()
    return endpoint, attempt.message_id


def test_it_delivers_again_under_a_new_id(no_real_network: list[httpx2.Request]) -> None:
    endpoint, original = _deliver_once()
    assert len(no_real_network) == 1

    replayed = replay_delivery(message_id=original)
    drain_outbox()

    # A new id, because a receiver deduplicates on webhook-id: replaying under
    # the original asks a well-behaved consumer to discard exactly the delivery
    # somebody asked for.
    assert replayed != original
    assert len(no_real_network) == 2
    assert no_real_network[1].headers["webhook-id"] == replayed


def test_the_replayed_body_carries_the_same_event(
    no_real_network: list[httpx2.Request],
) -> None:
    _, original = _deliver_once()
    replay_delivery(message_id=original)
    drain_outbox()

    document = Webhook(SECRET).verify(no_real_network[1].content, dict(no_real_network[1].headers))
    assert document["type"] == "testapp.OrderPlaced"
    assert document["data"]["order_id"] == 7


def test_it_is_signed_with_the_secret_in_force_now(
    no_real_network: list[httpx2.Request],
) -> None:
    # A replay is a new delivery, so it is signed the way a delivery minted now
    # is signed. Rotating between the two is the case that tells the difference:
    # the original body verifies only against the old secret, the replay against
    # both, and a replay signed from the log would verify against neither.
    endpoint, original = _deliver_once()
    new_secret = base64.b64encode(b"the-secret-it-rotated-to").decode()
    rotate_secret(endpoint, new_secret=new_secret)

    replay_delivery(message_id=original)
    drain_outbox()

    replayed = no_real_network[1]
    assert Webhook(new_secret).verify(replayed.content, dict(replayed.headers))


def test_it_renders_the_format_the_endpoint_is_pinned_to_now(
    no_real_network: list[httpx2.Request],
) -> None:
    # The pin is the consumer's integration contract as it stands today. If an
    # operator re-pinned the endpoint, the shape in the log is the one the
    # customer can no longer parse.
    endpoint, original = _deliver_once()
    Endpoint.objects.filter(pk=endpoint.pk).update(format_name="cloudevents", format_version=1)

    replay_delivery(message_id=original)
    drain_outbox()

    assert no_real_network[0].headers["content-type"] == "application/json"
    assert (
        no_real_network[1].headers["content-type"] == "application/cloudevents+json; charset=UTF-8"
    )


def test_the_replay_gets_its_own_log_rows(no_real_network: list[httpx2.Request]) -> None:
    # Through the substrate like any other delivery, so it has its own delivery
    # row, attempt budget and log rows rather than appending to the original's.
    _, original = _deliver_once()
    replayed = replay_delivery(message_id=original)
    drain_outbox()

    assert DeliveryAttempt.objects.filter(message_id=original).count() == 1
    assert DeliveryAttempt.objects.filter(message_id=replayed).count() == 1


def test_a_message_id_that_was_never_logged_is_refused() -> None:
    with pytest.raises(ReplayRefused, match="never logged"):
        replay_delivery(message_id="msg_no_such_delivery")


def test_a_deleted_endpoint_is_refused(no_real_network: list[httpx2.Request]) -> None:
    endpoint, original = _deliver_once()
    endpoint.delete()

    # The log row survives the endpoint on purpose -- it is evidence of where a
    # request went -- and that is not the same as a destination to send to.
    assert DeliveryAttempt.objects.filter(message_id=original).exists()
    with pytest.raises(ReplayRefused, match="has been deleted"):
        replay_delivery(message_id=original)


def test_an_inactive_endpoint_is_refused(no_real_network: list[httpx2.Request]) -> None:
    # Without this the replay is fired, claimed, and dropped by the receiver's
    # own is_active check: the operator sees a successful replay and the
    # customer receives nothing.
    endpoint, original = _deliver_once()
    Endpoint.objects.filter(pk=endpoint.pk).update(is_active=False)

    with pytest.raises(ReplayRefused, match="not active"):
        replay_delivery(message_id=original)


def test_a_pruned_event_is_refused(no_real_network: list[httpx2.Request]) -> None:
    # The bytes cannot be reconstructed without the event row, so this would
    # dead-letter after burning a whole attempt budget.
    _, original = _deliver_once()
    EventRecord.objects.filter(name="testapp.OrderPlaced").delete()

    with pytest.raises(ReplayRefused, match="Retention has outrun replay"):
        replay_delivery(message_id=original)


def test_nothing_is_posted_before_the_relay_runs(
    no_real_network: list[httpx2.Request],
) -> None:
    # It writes an event and returns. A replay that posted inline would do it
    # outside the substrate's retry, backoff and dead-lettering -- all the
    # machinery the replay is going through the substrate to get.
    _, original = _deliver_once()
    replay_delivery(message_id=original)
    assert len(no_real_network) == 1
