from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import models

from django_outbound_webhooks.models.value_too_long import ValueTooLong


class LengthCheckedCharField(models.CharField):
    """A `CharField` that refuses an over-long value on every save, not only in `full_clean`.

    Migrations see a plain `CharField`, so no `AlterField` (SQLite rebuilds the table)."""

    def __init__(self, *args: Any, max_length: int, **kwargs: Any) -> None:
        super().__init__(*args, max_length=max_length, **kwargs)
        self.limit = max_length

    def pre_save(self, model_instance: models.Model, add: bool) -> Any:
        value = super().pre_save(model_instance, add)
        # Expression: test_a_tenant_written_as_an_expression_*; `>`: *_exactly_at_the_limit_*.
        if isinstance(value, str) and len(value) > self.limit:
            raise ValueTooLong(
                model=type(model_instance).__name__,
                field=self.name,
                length=len(value),
                limit=self.limit,
            )
        return value

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, _, args, kwargs = super().deconstruct()
        return name, "django.db.models.CharField", args, kwargs
