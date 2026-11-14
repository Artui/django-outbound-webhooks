from __future__ import annotations

import base64
import contextlib
from collections.abc import Callable

import pytest
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import DataError, connection, transaction
from django.db.models import Value
from django.db.transaction import TransactionManagementError

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


def _update(endpoint: Endpoint) -> None:
    Endpoint.objects.update(tenant=endpoint.tenant)


def _bulk_update(endpoint: Endpoint) -> None:
    Endpoint.objects.bulk_update([endpoint], ["tenant"])


def _raw_save(endpoint: Endpoint) -> None:
    for loaded in serializers.deserialize("json", serializers.serialize("json", [endpoint])):
        loaded.save()


@pytest.mark.parametrize("write", [_update, _raw_save])
def test_writes_that_skip_pre_save_meet_the_database_instead(write: Callable[..., None]) -> None:
    endpoint = _endpoint()
    endpoint.save()
    endpoint.tenant = "t" * 300
    if connection.vendor == "sqlite":
        write(endpoint)
        assert len(Endpoint.objects.get().tenant) == 300
    else:
        with pytest.raises(DataError), transaction.atomic():
            write(endpoint)


def test_bulk_update_skips_pre_save_and_postgres_truncates_through_its_cast() -> None:
    endpoint = _endpoint()
    endpoint.save()
    endpoint.tenant = "t" * 300
    _bulk_update(endpoint)
    expected = 300 if connection.vendor == "sqlite" else _tenant_limit()
    assert len(Endpoint.objects.get().tenant) == expected


def test_a_stored_over_long_tenant_is_refused_by_update_or_create_that_leaves_it() -> None:
    if connection.vendor != "sqlite":
        pytest.skip("only SQLite can hold an over-long tenant")
    _endpoint(name="Acme").save()
    Endpoint.objects.update(tenant="t" * 300)
    with pytest.raises(ValueTooLong):
        Endpoint.objects.update_or_create(name="Acme", defaults={"format_version": 2})


def test_a_caller_catching_the_error_keeps_its_transaction_with_its_own_atomic() -> None:
    with transaction.atomic():
        with contextlib.suppress(ValueTooLong), transaction.atomic():
            Endpoint.objects.create(**_fields(tenant="t" * 300))
        Endpoint.objects.create(**_fields(tenant="acme"))
    assert list(Endpoint.objects.values_list("tenant", flat=True)) == ["acme"]


def test_a_caller_catching_the_error_without_its_own_atomic_loses_the_transaction() -> None:
    with transaction.atomic():
        with contextlib.suppress(ValueTooLong):
            Endpoint.objects.create(**_fields(tenant="t" * 300))
        with pytest.raises(TransactionManagementError):
            Endpoint.objects.create(**_fields(tenant="acme"))
