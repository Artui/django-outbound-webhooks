from __future__ import annotations


class UnsafeDestination(Exception):
    """The endpoint's URL resolves somewhere a webhook must not reach."""
