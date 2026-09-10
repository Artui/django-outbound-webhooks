"""A destination this package refuses to connect to."""

from __future__ import annotations


class UnsafeDestination(Exception):
    """The endpoint's URL resolves somewhere a webhook must not reach.

    Deliberately not an ``httpx2.HTTPError``. ``send_once`` turns transport
    errors into a retryable verdict, and retrying this one is pointless: the
    address will be just as unsafe on the next attempt, and each attempt is
    another connection to somewhere inside the network.
    """
