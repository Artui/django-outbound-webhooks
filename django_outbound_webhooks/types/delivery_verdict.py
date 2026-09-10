"""What one HTTP attempt means for whether to try again."""

from __future__ import annotations

import enum


class DeliveryVerdict(enum.Enum):
    """The three answers an endpoint's response can give.

    A webhook's outcome is a **status code**, which is a return value rather than
    an exception, and that is the whole reason this exists. The substrate can
    only retry what raises, so it retries everything to the attempt budget and a
    receiver has no way to say a failure is terminal. Modelling the verdict as
    data is what lets the inner policy branch on it, and it is the same
    classification auto-disable-on-rot will consult.
    """

    SUCCEEDED = "succeeded"

    RETRY = "retry"
    """Worth trying again: the endpoint was busy, unreachable, or broken in a
    way that is usually temporary."""

    PERMANENT = "permanent"
    """Not worth trying again. The endpoint is gone, or refused the request in a
    way that repeating cannot fix."""
