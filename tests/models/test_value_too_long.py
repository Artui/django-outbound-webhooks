from __future__ import annotations

from django_outbound_webhooks.models.value_too_long import ValueTooLong


def test_it_carries_the_field_and_its_limit_and_says_both() -> None:
    error = ValueTooLong(model="Endpoint", field="tenant", length=300, limit=255)
    assert (error.model, error.field, error.length, error.limit) == ("Endpoint", "tenant", 300, 255)
    assert str(error).startswith("Endpoint.tenant is 300 characters long and holds at most 255.")
    assert isinstance(error, ValueError)
