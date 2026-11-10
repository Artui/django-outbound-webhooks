from __future__ import annotations

import enum


class DeliveryVerdict(enum.Enum):
    """The three answers an endpoint's response can give."""

    SUCCEEDED = "succeeded"

    RETRY = "retry"
    """Worth trying again: the endpoint was busy, unreachable, or broken in a
    way that is usually temporary."""

    PERMANENT = "permanent"
    """Not worth trying again. The endpoint is gone, or refused the request in a
    way that repeating cannot fix."""
