"""Every secret one endpoint's deliveries should be signed with."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_outbound_webhooks.models.endpoint import Endpoint


def signing_secrets(endpoint: Endpoint) -> list[str]:
    """The secrets to sign with, newest first.

    A list from the first release even though there is one column today. The
    specification carries several signatures in one header and that is how a
    secret rotates without a coordinated cutover, so callers are written against
    the shape rotation needs rather than the shape one column suggests.

    Out here rather than on the model because of what it becomes: rotation adds
    a second column *and a window*, and a window is a policy with a clock in it.
    That is the kind of thing that grows quietly once it has a method to grow in.
    """
    return [endpoint.secret]
