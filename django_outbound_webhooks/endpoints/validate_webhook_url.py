"""Refuse a destination that is not an HTTP URL."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

#: Delivering to anything else is not a feature with a missing implementation,
#: it is a different product. Naming the two schemes rather than accepting
#: whatever URLField allows keeps file:// and friends out of a column a customer
#: writes.
ALLOWED_SCHEMES = ("http", "https")


def validate_webhook_url(value: str) -> None:
    """A field validator, so every form, serializer and admin path gets it free."""
    scheme = urlsplit(value).scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            "A webhook endpoint has to be an http or https URL; got %(scheme)r.",
            code="invalid_scheme",
            params={"scheme": scheme},
        )
