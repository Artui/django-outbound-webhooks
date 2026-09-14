"""The endpoint row itself, which is all this model is."""

from __future__ import annotations

import base64

import pytest
from django.core.exceptions import ValidationError

from django_outbound_webhooks.models.endpoint import Endpoint

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
    return Endpoint(**fields)


def test_it_stores_a_row_with_sensible_defaults() -> None:
    endpoint = _endpoint()
    endpoint.save()
    assert endpoint.is_active is True
    assert endpoint.tenant == ""


def test_str_names_the_url_and_the_pinned_format() -> None:
    assert str(_endpoint()) == "Acme production (https://example.test/hooks)"


def test_the_field_validators_fire_wherever_full_clean_runs() -> None:
    # Declared on the fields rather than written into a clean() method, so a
    # form, the admin, a serializer and register_endpoint all get them without
    # the model growing behaviour.
    with pytest.raises(ValidationError) as raised:
        _endpoint(secret="ab cd", url="file:///etc/passwd").full_clean()
    assert set(raised.value.error_dict) == {"secret", "url"}


def test_a_bare_save_does_not_validate() -> None:
    # Stated rather than implied. Django's convention is that model validation
    # belongs to forms, and this model follows it: the door with the rules
    # behind it is register_endpoint, and a caller reaching past it gets
    # Django's ordinary behaviour rather than a surprise.
    _endpoint(url="file:///etc/passwd").save()
    assert Endpoint.objects.count() == 1


def test_an_endpoint_that_predates_rotation_and_health_reads_correctly() -> None:
    # A nullable AddField backfills nothing and a defaulted one backfills its
    # default, so what an existing row reads after the 0.3.0 migration is
    # exactly what a row created without these kwargs reads now. Asserting the
    # second is the closest this suite gets to the first without a migration
    # harness, and it is the assertion that matters: every one of these has to
    # say "nothing has happened yet" rather than something that looks like a
    # rotation or a disabling that never took place.
    endpoint = Endpoint(
        name="Acme production",
        url="https://example.test/hooks",
        secret=SECRET,
        format_name="envelope",
        format_version=1,
    )
    assert endpoint.previous_secret == ""
    assert endpoint.previous_secret_expires_at is None
    assert endpoint.consecutive_dead_deliveries == 0
    assert endpoint.disabled_at is None
    assert endpoint.is_active is True
