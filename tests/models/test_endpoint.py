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
    with pytest.raises(ValidationError) as raised:
        _endpoint(secret="ab cd", url="file:///etc/passwd").full_clean()
    assert set(raised.value.error_dict) == {"secret", "url"}


def test_a_bare_save_does_not_validate() -> None:
    # Stated rather than implied.
    _endpoint(url="file:///etc/passwd").save()
    assert Endpoint.objects.count() == 1


def test_an_endpoint_that_predates_rotation_and_health_reads_correctly() -> None:
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
