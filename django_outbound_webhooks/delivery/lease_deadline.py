from __future__ import annotations


def lease_deadline(*, lease_seconds: float, timeout_seconds: float, margin_seconds: float) -> float:
    """The elapsed time after which no further attempt may be *started*."""
    deadline = lease_seconds - timeout_seconds - margin_seconds
    if deadline <= 0:
        raise ValueError(
            f"There is no room to retry inside the lease: a {lease_seconds}s lease cannot hold "
            f"a {timeout_seconds}s request plus a {margin_seconds}s margin. Raise "
            f"lease_seconds on the receiver, or lower TIMEOUT_SECONDS."
        )
    return deadline
