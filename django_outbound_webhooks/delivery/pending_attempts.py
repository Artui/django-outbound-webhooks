"""The attempts one delivery has made, waiting to be written."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue
    from django_outbound_webhooks.types.attempt_outcome import AttemptOutcome


@dataclass(slots=True)
class PendingAttempts:
    """What the log needs, held until whichever path survives can write it."""

    due: WebhookDeliveryDue
    url: str
    outer_attempt: int
    request_body_sha256: str
    request_body_bytes: int
    outcomes: list[AttemptOutcome]


#: Set by the delivery receiver, read by whichever of the two paths gets to
#: write. A context variable rather than an argument because the failure path
#: is not called by us: the substrate calls the ``on_failure`` hook after the
#: receiver has already raised and its transaction has been rolled back, and it
#: hands over an identity, not the attempts. This is the only channel between
#: the two.
#:
#: Never reset in a ``finally``. The hook runs *after* the receiver returns, so
#: clearing on the way out would empty it before the only reader looks. Each
#: delivery sets it first thing instead, which is what keeps a stale one from
#: outliving its usefulness.
pending_attempts: ContextVar[PendingAttempts | None] = ContextVar(
    "django_outbound_webhooks_pending_attempts", default=None
)
