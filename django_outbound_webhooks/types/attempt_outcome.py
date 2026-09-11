"""What one HTTP attempt did, beyond whether it worked."""

from __future__ import annotations

from dataclasses import dataclass

from django_outbound_webhooks.types.delivery_verdict import DeliveryVerdict


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    """One request, its answer, and how long it took.

    Carried in memory rather than written as it happens, because a receiver's
    writes are discarded when it raises: the attempts most worth recording are
    exactly the ones that cannot record themselves. These accumulate and are
    written once, by whichever path survives.
    """

    verdict: DeliveryVerdict
    duration_ms: int

    status_code: int | None = None
    """None when nothing answered, which is what a transport error looks like."""

    response_body: str = ""
    """Truncated. An endpoint's error page is for a human reading the log, and
    an untruncated one is a customer's HTML in every row."""

    error: str = ""
    """The transport error, when there was no response at all."""
