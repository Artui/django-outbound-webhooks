"""The customer-owned endpoint row, and the two ways it fails silently."""

from __future__ import annotations

import base64

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from standardwebhooks import Webhook

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.types.format_id import FormatId

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _endpoint(**overrides: object) -> Endpoint:
    fields: dict[str, object] = {
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "format_name": "envelope",
        "format_version": 1,
    }
    fields.update(overrides)
    return Endpoint(**fields)


def test_it_saves_and_reports_the_format_it_is_pinned_to() -> None:
    endpoint = _endpoint()
    endpoint.save()
    assert endpoint.format_id == FormatId(name="envelope", version=1)
    assert endpoint.is_active is True


def test_signing_secrets_is_a_list_before_rotation_exists() -> None:
    # One column today, and the caller is written against the shape rotation
    # needs so that adding the second column changes no call site.
    assert _endpoint().signing_secrets() == [SECRET]


@pytest.mark.parametrize("scheme", ["ftp://example.test/x", "file:///etc/passwd", "/relative"])
def test_a_url_that_is_not_http_is_refused(scheme: str) -> None:
    with pytest.raises(ValidationError, match="http or https"):
        _endpoint(url=scheme).save()


def test_a_secret_the_library_would_silently_mangle_is_refused() -> None:
    # The sharpest case, and the reason this check exists at all. The signing
    # library decodes with validate=False, so a secret containing a character
    # outside the base64 alphabet is not rejected -- the character is discarded
    # and the rest decodes to different bytes entirely. It signs happily, and
    # only the customer's verification fails, on their side, with no signal on
    # ours.
    mangled = "ab cd"
    Webhook(mangled)  # the library accepts it, which is the whole problem
    with pytest.raises(ValidationError, match="has to be base64"):
        _endpoint(secret=mangled).save()


@pytest.mark.parametrize(
    "secret",
    [
        SECRET,
        f"whsec_{SECRET}",
        SECRET.rstrip("="),
    ],
)
def test_every_spelling_the_library_accepts_is_accepted_here(secret: str) -> None:
    # The check must never be stricter than the library on a working secret,
    # or it refuses registrations that would have delivered fine.
    _endpoint(secret=secret).save()


@pytest.mark.parametrize("secret", ["", "whsec_", "====", "not base64!!"])
def test_a_secret_that_cannot_produce_bytes_is_refused(secret: str) -> None:
    with pytest.raises(ValidationError, match="has to be base64"):
        _endpoint(secret=secret).save()


def test_saving_validates_without_being_asked() -> None:
    # Django leaves model validation to forms, and that convention assumes a
    # developer is writing the row. These rows come from a self-service surface
    # on a customer's behalf, and the checks above are silent when they fail.
    with pytest.raises(ValidationError):
        Endpoint.objects.create(
            url="https://example.test/x", secret="ab cd", format_name="envelope", format_version=1
        )
    assert Endpoint.objects.count() == 0


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"TENANT_SCOPE_KEY": "tenant"})
def test_a_tenanted_deployment_refuses_an_endpoint_with_no_tenant() -> None:
    with pytest.raises(ValidationError, match="has to name the tenant"):
        _endpoint().save()


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"TENANT_SCOPE_KEY": "tenant"})
def test_a_tenanted_endpoint_saves() -> None:
    _endpoint(tenant="acme").save()
    assert Endpoint.objects.get().tenant == "acme"


def test_an_untenanted_deployment_does_not_demand_one() -> None:
    # A single-tenant deployment is a real deployment, and it is chosen in
    # settings rather than inferred from a blank column.
    _endpoint().save()
    assert Endpoint.objects.get().tenant == ""


def test_str_names_the_url_and_the_pinned_format() -> None:
    assert str(_endpoint()) == "https://example.test/hooks (envelope@1)"
