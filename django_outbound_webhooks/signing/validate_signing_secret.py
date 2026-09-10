"""Refuse a signing secret the specification's library would silently mangle."""

from __future__ import annotations

import base64
import binascii

from django.core.exceptions import ValidationError


def validate_signing_secret(value: str) -> None:
    """Require real base64, because the signing library does not.

    This is the quietest failure in the package. ``Webhook`` decodes the secret
    with ``validate=False``, so any character outside the base64 alphabet is
    **discarded** and whatever is left decodes to different bytes entirely. It
    then signs without complaint. Nothing fails here, nothing fails at delivery,
    and only the customer's verification fails -- on their side, with no signal
    on ours.

    Calibrated against the library rather than against the specification: of the
    malformed secrets the library rejects outright this agrees, and the one it
    *accepts* is exactly the one being guarded.

    Padding is normalised rather than appended. The library appends ``"=="``
    unconditionally, and ``validate=True`` rejects that on an already-padded
    secret as excess data -- so the obvious spelling of this check refuses every
    ordinary secret.
    """
    candidate = value.removeprefix("whsec_")
    if candidate:
        padded = candidate + "=" * (-len(candidate) % 4)
        try:
            base64.b64decode(padded, validate=True)
        except (ValueError, binascii.Error):
            pass
        else:
            return

    # No "did it decode to any bytes?" check here, and its absence is
    # deliberate. It was written, and coverage showed the branch could never be
    # taken: only a zero-length input decodes to nothing, and the guard above
    # has already excluded that. An unreachable branch is a signal to
    # restructure rather than to exempt.

    raise ValidationError(
        "The signing secret has to be base64. The signing library decodes it without "
        "checking, so a secret that is not base64 silently signs with different bytes and "
        "every delivery fails verification on the customer's side.",
        code="not_base64",
    )
