"""One customer-registered destination for webhook deliveries."""

from __future__ import annotations

import base64
import binascii
from typing import Any
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models

from django_outbound_webhooks.settings import setting
from django_outbound_webhooks.types.format_id import FormatId

#: Delivering to anything but HTTP is not a feature with a missing
#: implementation, it is a different product. Naming the two schemes here rather
#: than accepting whatever ``URLField`` does keeps ``file://`` and friends out of
#: a column a customer writes.
ALLOWED_SCHEMES = ("http", "https")


class Endpoint(models.Model):
    """Where one customer wants deliveries, in the shape they integrated against.

    Customer-owned: the rows here are written through a product surface, not by
    an operator editing settings, which is why validation is enforced on save
    rather than left to whichever call site happens to remember it.
    """

    url = models.URLField(max_length=2000)
    secret = models.CharField(
        max_length=255,
        help_text="Base64, optionally with the whsec_ prefix the specification uses.",
    )

    #: Pinned at registration and then frozen. The endpoint stops following the
    #: latest version the moment it is created, because the bytes it receives
    #: are what its owner wrote code against.
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    #: The customer this endpoint belongs to, matched against the event's scope.
    #: Blank only where the deployment has no tenancy at all; see
    #: ``TENANT_SCOPE_KEY``.
    tenant = models.CharField(max_length=255, blank=True, db_index=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "tenant"])]

    def __str__(self) -> str:
        return f"{self.url} ({self.format_id})"

    @property
    def format_id(self) -> FormatId:
        """The published format version this endpoint is pinned to."""
        return FormatId(name=self.format_name, version=self.format_version)

    def signing_secrets(self) -> list[str]:
        """Every secret a delivery should be signed with, newest first.

        A list from the first release even though there is one column today.
        The specification carries several signatures in one header and that is
        how a secret rotates without a coordinated cutover, so the caller is
        written against the shape rotation needs rather than against the shape
        one column suggests.
        """
        return [self.secret]

    def clean(self) -> None:
        errors: dict[str, Any] = {}

        scheme = urlsplit(self.url).scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            errors["url"] = ValidationError(
                "A webhook endpoint has to be an http or https URL; got %(scheme)r.",
                params={"scheme": scheme},
            )

        if not _is_base64(self.secret):
            # The signing library base64-decodes the secret and does not check
            # it, so a secret that is not base64 decodes to something else
            # entirely and signs happily. Nothing fails here or at delivery --
            # only the customer's verification fails, on their side, with no
            # signal on ours. It is the quietest way to break this package.
            errors["secret"] = ValidationError(
                "The signing secret has to be base64. The signing library decodes it without "
                "checking, so a secret that is not base64 silently signs with different bytes "
                "and every delivery fails verification on the customer's side."
            )

        tenant_key = setting("TENANT_SCOPE_KEY")
        if tenant_key is not None and not self.tenant:
            errors["tenant"] = ValidationError(
                "This deployment scopes events by %(key)r, so an endpoint has to name the "
                "tenant it belongs to. An endpoint with no tenant would either receive "
                "everyone's events or nobody's, and neither is a default worth having.",
                params={"key": tenant_key},
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Validate on the way in, always.

        Django's convention leaves model validation to forms, and that
        convention assumes the writer is a developer. These rows are written by
        a self-service product surface on a customer's behalf, and two of the
        checks above are silent when they fail: an unverifiable secret, and a
        tenant that decides whose data reaches whose URL. A row that skipped
        validation is indistinguishable from a valid one until a customer
        reports that nothing works.

        The cost is real and worth stating: this bypasses nothing, so
        ``bulk_create`` and ``loaddata`` do not run these checks, and a fixture
        carrying a bad secret will load.
        """
        self.full_clean()
        super().save(*args, **kwargs)


def _is_base64(secret: str) -> bool:
    """Whether this secret decodes to the bytes it looks like.

    ``validate=True`` is the whole point. Without it -- which is how the signing
    library calls it -- base64 silently discards every character outside the
    alphabet and decodes whatever is left, so ``"ab cd"`` becomes three
    arbitrary bytes and signs without complaint. Measured against the library:
    of the malformed secrets it rejects outright, this agrees; the one it
    *accepts* is exactly the one this exists to catch.

    Padding is normalised rather than appended. The library appends ``"=="``
    unconditionally, which ``validate=True`` then rejects on an
    already-padded secret as excess data, so a check written that way would
    refuse the ordinary case and accept nothing.
    """
    candidate = secret.removeprefix("whsec_")
    if not candidate:
        return False
    padded = candidate + "=" * (-len(candidate) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (ValueError, binascii.Error):
        return False
    # A secret that decodes to nothing is one the library refuses at
    # construction, hours later and somewhere else.
    return bool(decoded)
