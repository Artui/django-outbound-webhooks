"""How long the inner retry may run before the lease is at risk."""

from __future__ import annotations


def lease_deadline(*, lease_seconds: float, timeout_seconds: float, margin_seconds: float) -> float:
    """The elapsed time after which no further attempt may be *started*.

    This is the whole reason the inner tier is a deadline rather than an attempt
    count. A receiver runs inside the transaction that carries its own
    acknowledgement and cannot extend its lease from the inside, so a policy
    unbounded in time can outlast the lease with the POST already sent. Another
    worker then takes the row and this worker's write is rolled back: the
    customer has the delivery and the log does not. A retry policy that
    manufactures duplicate deliveries is worse than no retry policy.

    The arithmetic is the part that is easy to get subtly wrong, and getting it
    wrong reintroduces exactly the failure being guarded against.
    ``stop_before_delay`` keeps the next *sleep* inside the limit it is given and
    knows nothing about how long the attempt after that sleep will run. So the
    limit has to be the lease **minus one whole timeout**, or the last attempt
    can begin a hair under the deadline and still run for the full timeout past
    it. The margin covers what neither number describes: clock skew, connection
    setup, and the substrate's own bookkeeping either side of the receiver.

    Refuses rather than clamping. A configuration where a single request may run
    longer than the lease has no safe policy at all, and quietly substituting
    zero would turn "retry once or twice" into "never retry" with nothing said.
    """
    deadline = lease_seconds - timeout_seconds - margin_seconds
    if deadline <= 0:
        raise ValueError(
            f"There is no room to retry inside the lease: a {lease_seconds}s lease cannot hold "
            f"a {timeout_seconds}s request plus a {margin_seconds}s margin. Raise "
            f"lease_seconds on the receiver, or lower TIMEOUT_SECONDS."
        )
    return deadline
