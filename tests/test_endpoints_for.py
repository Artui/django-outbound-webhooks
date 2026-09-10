"""Which endpoints an event is owed to, and every way that could widen."""

from __future__ import annotations

import base64

import pytest

from django_outbound_webhooks.endpoints_for import endpoints_for
from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.subscription import Subscription

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _subscribed(event_name: str = "shop.OrderPlaced", **overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "format_name": "envelope",
        "format_version": 1,
    }
    fields.update(overrides)
    endpoint = Endpoint.objects.create(**fields)
    Subscription.objects.create(endpoint=endpoint, event_name=event_name)
    return endpoint


def test_a_subscribed_endpoint_matches() -> None:
    endpoint = _subscribed()
    assert list(endpoints_for(event_name="shop.OrderPlaced", scope={})) == [endpoint]


def test_an_endpoint_subscribed_to_something_else_does_not() -> None:
    _subscribed(event_name="shop.OrderShipped")
    assert list(endpoints_for(event_name="shop.OrderPlaced", scope={})) == []


def test_an_inactive_endpoint_does_not() -> None:
    _subscribed(is_active=False)
    assert list(endpoints_for(event_name="shop.OrderPlaced", scope={})) == []


def test_each_endpoint_appears_once() -> None:
    # The join could duplicate an endpoint if it held two matching
    # subscriptions. The unique constraint is what prevents it, and this is
    # what would notice if the constraint were dropped.
    endpoint = _subscribed()
    Subscription.objects.create(endpoint=endpoint, event_name="shop.OrderShipped")
    assert list(endpoints_for(event_name="shop.OrderPlaced", scope={})) == [endpoint]


class TestWithoutTenancy:
    """TENANT_SCOPE_KEY is None: a single-tenant deployment, chosen in settings."""

    def test_scope_is_ignored(self) -> None:
        endpoint = _subscribed()
        matched = endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": "anything"})
        assert list(matched) == [endpoint]


class TestWithTenancy:
    """TENANT_SCOPE_KEY is set: the boundary that decides whose data goes where."""

    @pytest.fixture(autouse=True)
    def _tenanted(self, settings: object) -> None:
        # pytest-django's settings fixture rather than override_settings as a
        # class decorator: that form only works on a Django TestCase subclass
        # and raises at collection here.
        settings.DJANGO_OUTBOUND_WEBHOOKS = {"TENANT_SCOPE_KEY": "tenant"}

    def test_only_the_matching_tenant_matches(self) -> None:
        acme = _subscribed(tenant="acme")
        _subscribed(tenant="globex")
        assert list(endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": "acme"})) == [
            acme
        ]

    @pytest.mark.parametrize(
        ("label", "scope"),
        [
            ("missing", {}),
            ("null", {"tenant": None}),
            ("blank", {"tenant": ""}),
            ("another key entirely", {"organisation": "acme"}),
        ],
        ids=lambda value: value if isinstance(value, str) else "",
    )
    def test_an_event_with_no_usable_tenant_matches_nothing(
        self, label: str, scope: dict[str, object]
    ) -> None:
        # The case worth being deliberate about. An event fired outside a
        # request, by a management command, or by anything that forgot to open
        # an attributed() block arrives with an empty scope. Reading that as
        # "no filter" would send one customer's payload to every customer, and
        # it would look like a successful delivery from every angle.
        #
        # Two tenants exist here on purpose: with one, a fail-open would return
        # the same single row as a correct match and the test would pass either
        # way.
        _subscribed(tenant="acme")
        _subscribed(tenant="globex")
        assert list(endpoints_for(event_name="shop.OrderPlaced", scope=scope)) == []

    def test_a_blank_tenant_column_is_not_a_wildcard(self) -> None:
        # tenant is a blankable column, so an event carrying an empty string
        # must not match every endpoint that never set one. Belt and braces:
        # the model refuses to save such an endpoint under tenancy, so this
        # builds one the way a migration from an untenanted deployment would.
        Endpoint.objects.filter(pk=_subscribed(tenant="acme").pk).update(tenant="")
        assert list(endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": ""})) == []

    def test_an_integer_tenant_in_the_scope_matches_a_text_column(self) -> None:
        # A characterisation test, not a guard: it pins behaviour this package
        # depends on and does not implement. An event's scope is JSON and
        # usually carries an integer primary key while the column is text, and
        # CharField.get_prep_value is what coerces. Writing our own str() beside
        # it was tried and removed -- mutating it out changed nothing, so it was
        # a line that could only ever be trusted for a reason it did not have.
        # This test goes red if Django ever stops coercing, which is the only
        # way that dependency could break.
        endpoint = _subscribed(tenant="42")
        assert list(endpoints_for(event_name="shop.OrderPlaced", scope={"tenant": 42})) == [
            endpoint
        ]
