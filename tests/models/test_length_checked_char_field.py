from __future__ import annotations

from django.db import models

from django_outbound_webhooks.models.length_checked_char_field import LengthCheckedCharField


def test_migrations_record_it_as_a_plain_char_field() -> None:
    _, path, _, kwargs = LengthCheckedCharField(max_length=7, blank=True).deconstruct()
    assert path == "django.db.models.CharField"
    assert kwargs == {"max_length": 7, "blank": True}
    assert isinstance(LengthCheckedCharField(max_length=7), models.CharField)
