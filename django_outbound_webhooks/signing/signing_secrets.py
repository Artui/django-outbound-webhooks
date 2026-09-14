"""Every secret one endpoint's deliveries should be signed with."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def signing_secrets(endpoint: Endpoint) -> list[str]:
    """The secrets to sign with, newest first.

    A list since the first release, when there was one column. The
    specification carries several signatures in one header and that is how a
    secret rotates without a coordinated cutover, so callers were written
    against the shape rotation needs rather than the shape one column suggests.
    Rotation has since arrived and nothing downstream changed.

    Out here rather than on the model because of what it became: rotation added
    a second column *and a window*, and a window is a policy with a clock in it.
    That is the kind of thing that grows quietly once it has a method to grow in.

    Both halves of the condition earn their place, and one of them guards a row
    this package never writes. ``rotate_secret`` sets the secret and the expiry
    together, but a column is editable by anything with a database connection,
    and an expiry left standing over a blank previous secret would otherwise
    sign every delivery with the empty string -- which is a signature the
    customer cannot verify and cannot explain.
    """
    secrets = [endpoint.secret]
    expires_at = endpoint.previous_secret_expires_at
    if endpoint.previous_secret and expires_at is not None and expires_at > timezone.now():
        secrets.append(endpoint.previous_secret)
    return secrets
