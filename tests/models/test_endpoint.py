from __future__ import annotations

import base64
import contextlib

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Value

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.value_too_long import ValueTooLong

SECRET = base64.b64encode(b"a-signing-secret-of-some-length").decode()

pytestmark = pytest.mark.django_db


def _fields(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "name": "Acme production",
        "url": "https://example.test/hooks",
        "secret": SECRET,
        "format_name": "envelope",
        "format_version": 1,
    }
    fields.update(overrides)
    return fields


def _endpoint(**overrides: object) -> Endpoint:
    return Endpoint(**_fields(**overrides))


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


def _tenant_limit() -> int:
    return Endpoint._meta.get_field("tenant").max_length


def _assert_names_tenant_and_limit(error: BaseException) -> None:
    assert "tenant" in str(error)
    assert str(_tenant_limit()) in str(error)


def test_create_refuses_an_over_long_tenant_before_any_sql(django_assert_num_queries) -> None:
    with django_assert_num_queries(0), pytest.raises(ValueTooLong) as raised:
        Endpoint.objects.create(**_fields(tenant="t" * (_tenant_limit() + 1)))
    _assert_names_tenant_and_limit(raised.value)


def test_save_refuses_an_over_long_tenant_before_any_sql(django_assert_num_queries) -> None:
    endpoint = _endpoint(tenant="t" * (_tenant_limit() + 1))
    with django_assert_num_queries(0), pytest.raises(ValueTooLong) as raised:
        endpoint.save()
    _assert_names_tenant_and_limit(raised.value)


def test_bulk_create_refuses_an_over_long_tenant_before_any_sql(django_assert_num_queries) -> None:
    rows = [_endpoint(tenant="acme"), _endpoint(tenant="t" * (_tenant_limit() + 1))]
    with django_assert_num_queries(0), pytest.raises(ValueTooLong):
        Endpoint.objects.bulk_create(rows)
    assert not Endpoint.objects.exists()


def test_update_or_create_refuses_an_over_long_tenant_in_its_defaults() -> None:
    _endpoint(name="Acme").save()
    with pytest.raises(ValueTooLong):
        Endpoint.objects.update_or_create(name="Acme", defaults={"tenant": "t" * 300})
    assert Endpoint.objects.get().tenant == ""


def test_a_tenant_exactly_at_the_limit_is_stored() -> None:
    endpoint = Endpoint.objects.create(**_fields(tenant="t" * _tenant_limit()))
    endpoint.refresh_from_db()
    assert len(endpoint.tenant) == _tenant_limit()


def test_a_tenant_written_as_an_expression_is_left_to_the_database() -> None:
    endpoint = Endpoint.objects.create(**_fields(tenant=Value("acme")))
    endpoint.refresh_from_db()
    assert endpoint.tenant == "acme"


def test_update_and_bulk_update_skip_the_check_and_meet_the_database() -> None:
    endpoint = _endpoint()
    endpoint.save()
    endpoint.tenant = "t" * 300
    with contextlib.suppress(DatabaseError), transaction.atomic():
        Endpoint.objects.update(tenant="t" * 300)
    with contextlib.suppress(DatabaseError), transaction.atomic():
        Endpoint.objects.bulk_update([endpoint], ["tenant"])
