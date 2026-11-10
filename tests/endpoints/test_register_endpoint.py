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
    endpoint = _register(event_names=["shop.OrderPlaced", "shop.OrderPlaced"])
    assert endpoint.subscriptions.count() == 1


def test_no_event_names_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        _register(event_names=[])
    assert raised.value.code == "no_subscriptions"
    assert Endpoint.objects.count() == 0


def test_an_unpinned_registration_pins_the_latest_and_records_it() -> None:
    # "No version given" does not mean "follow the latest".
    endpoint = _register()
    assert endpoint.format_name == "envelope"
    assert endpoint.format_version == 1


def test_an_explicit_version_that_was_never_published_is_refused() -> None:
    with pytest.raises(LookupError, match="envelope@9"):
        _register(format_version=9)
    assert Endpoint.objects.count() == 0


def test_an_unknown_format_family_is_refused() -> None:
    # The name here has to be one nothing will ever publish.
    with pytest.raises(LookupError, match="'stone-tablet'"):
        _register(format_name="stone-tablet")


def test_the_second_built_in_family_can_be_pinned() -> None:
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
        # Worth pinning which kind of guard this is.
        from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for

        endpoint = _register(tenant="acme")
        Endpoint.objects.filter(pk=endpoint.pk).update(tenant="")
        matched = endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": "acme"})
        assert list(matched) == []


def test_the_name_is_what_identifies_an_endpoint_to_its_owner() -> None:
    endpoint = _register(name="Acme staging")
    assert str(endpoint) == "Acme staging (https://example.test/hooks)"


def test_two_endpoints_may_share_a_name() -> None:
    # Deliberately not unique.
    _register(name="production")
    _register(name="production", url="https://other.test/hooks")
    assert Endpoint.objects.filter(name="production").count() == 2
