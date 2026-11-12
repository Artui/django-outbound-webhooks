from __future__ import annotations

import enum


class DeliveryVerdict(enum.Enum):
    """The three answers an endpoint's response can give."""

    SUCCEEDED = "succeeded"

    RETRY = "retry"
    """Worth trying again: the endpoint was busy, unreachable, or broken in a
    way that is usually temporary."""

    PERMANENT = "permanent"
    """Not worth another request in this delivery: the endpoint is gone, or refused
    it in a way repeating cannot fix. The substrate still retries the delivery."""
