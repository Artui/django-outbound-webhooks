"""The supported way to add an endpoint, and the rules that live behind it."""

from __future__ import annotations

import base64

import pytest
from django.core.exceptions import ValidationError

from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.subscription import Subscription

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _register(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "event_names": ["shop.OrderPlaced"],
    }
    fields.update(overrides)
    return register_endpoint(**fields)


def test_it_creates_the_endpoint_and_its_subscriptions() -> None:
    endpoint = _register(event_names=["shop.OrderPlaced", "shop.OrderShipped"])
    assert Endpoint.objects.count() == 1
    assert sorted(endpoint.subscriptions.values_list("event_name", flat=True)) == [
        "shop.OrderPlaced",
        "shop.OrderShipped",
    ]


def test_a_repeated_event_name_is_subscribed_once() -> None:
    # A caller passing the same name twice is not an error worth refusing, and
    # the unique constraint would turn it into one.
    endpoint = _register(event_names=["shop.OrderPlaced", "shop.OrderPlaced"])
    assert endpoint.subscriptions.count() == 1


def test_no_event_names_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        _register(event_names=[])
    assert raised.value.code == "no_subscriptions"
    assert Endpoint.objects.count() == 0


def test_an_unpinned_registration_pins_the_latest_and_records_it() -> None:
    # "No version given" does not mean "follow the latest". It means pin
    # whatever is latest right now and write that number down, because an
    # endpoint whose version is implicit is the unnamed-default problem one
    # level down.
    endpoint = _register()
    assert endpoint.format_name == "envelope"
    assert endpoint.format_version == 1


def test_an_explicit_version_that_was_never_published_is_refused() -> None:
    # Fails at registration rather than at the first delivery, which would be
    # hours later and in another process.
    with pytest.raises(LookupError, match="envelope@9"):
        _register(format_version=9)
    assert Endpoint.objects.count() == 0


def test_an_unknown_format_family_is_refused() -> None:
    # The name here has to be one nothing will ever publish. It used to be
    # "cloudevents", which was unpublished when this was written and is a
    # shipped format now -- so the test asserted a refusal that had quietly
    # become a success, and said so by failing.
    with pytest.raises(LookupError, match="'stone-tablet'"):
        _register(format_name="stone-tablet")


def test_the_second_built_in_family_can_be_pinned() -> None:
    # The other half of the same question: an endpoint can select any published
    # family, and pinning one it did not name a version for records the version
    # it got.
    endpoint = _register(format_name="cloudevents")
    assert (endpoint.format_name, endpoint.format_version) == ("cloudevents", 1)


def test_an_invalid_secret_is_refused_and_nothing_is_written() -> None:
    with pytest.raises(ValidationError):
        _register(secret="ab cd")
    assert Endpoint.objects.count() == 0
    assert Subscription.objects.count() == 0


def test_an_invalid_url_is_refused_and_nothing_is_written() -> None:
    with pytest.raises(ValidationError):
        _register(url="file:///etc/passwd")
    assert Endpoint.objects.count() == 0


class TestWithTenancy:
    @pytest.fixture(autouse=True)
    def _tenanted(self, settings: object) -> None:
        settings.DJANGO_OUTBOUND_WEBHOOKS = {
            "TENANT_SCOPE_KEY": "tenant",
            "DEFAULT_FORMAT": "envelope",
        }

    def test_a_registration_with_no_tenant_is_refused(self) -> None:
        with pytest.raises(ValidationError) as raised:
            _register()
        assert raised.value.code == "tenant_required"

    def test_a_tenanted_registration_succeeds(self) -> None:
        assert _register(tenant="acme").tenant == "acme"

    def test_the_refusal_is_ergonomic_rather_than_protective(self) -> None:
        # Worth pinning which kind of guard this is. An endpoint with no tenant
        # already receives nothing under tenancy, because matching filters on a
        # non-blank value and a blank column can never equal one. The refusal
        # stops an operator creating a row that silently never fires; it does
        # not close a hole.
        from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for

        endpoint = _register(tenant="acme")
        Endpoint.objects.filter(pk=endpoint.pk).update(tenant="")
        matched = endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": "acme"})
        assert list(matched) == []


def test_the_name_is_what_identifies_an_endpoint_to_its_owner() -> None:
    # A customer with several endpoints has no other way to tell them apart:
    # a URL is long and a primary key means nothing to them.
    endpoint = _register(name="Acme staging")
    assert str(endpoint) == "Acme staging (https://example.test/hooks)"


def test_two_endpoints_may_share_a_name() -> None:
    # Deliberately not unique. A uniqueness refusal on a field a customer types
    # is one they cannot act on when the clash is with a row they cannot see.
    _register(name="production")
    _register(name="production", url="https://other.test/hooks")
    assert Endpoint.objects.filter(name="production").count() == 2
