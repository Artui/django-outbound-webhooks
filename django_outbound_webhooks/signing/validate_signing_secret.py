from __future__ import annotations

import base64
import binascii

from django.core.exceptions import ValidationError


def validate_signing_secret(value: str) -> None:
    """Require real base64, because the signing library does not."""
    candidate = value.removeprefix("whsec_")
    if candidate:
        padded = candidate + "=" * (-len(candidate) % 4)
        try:
            base64.b64decode(padded, validate=True)
        except (ValueError, binascii.Error):
            pass
        else:
            return

    raise ValidationError(
        "The signing secret has to be base64. The signing library decodes it without "
        "checking, so a secret that is not base64 silently signs with different bytes and "
        "every delivery fails verification on the customer's side.",
        code="not_base64",
    )
