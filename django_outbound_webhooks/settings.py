"""Settings this package reads, and their defaults.

One namespaced dict rather than a scatter of top-level names, so a project can
see everything this package reads in one place and a typo in a key raises here
rather than silently taking a default.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

SETTINGS_NAME = "DJANGO_OUTBOUND_WEBHOOKS"

DEFAULTS: dict[str, Any] = {
    # The format an endpoint is pinned to when it registers without naming one.
    # A registration with no stated version pins the latest and records which
    # one that was: an endpoint whose format is implicit is the unnamed-default
    # problem one level down, and it is the problem this package exists not to
    # hand its customers.
    "DEFAULT_FORMAT": "envelope",
    # Which key in an event's scope names the customer an event belongs to, or
    # None for a deployment that has no such notion.
    #
    # This is the isolation boundary, so it is a deployment-level decision
    # rather than a per-row default. With a key configured, an endpoint must
    # name a tenant and an event must carry that key, and an event that does not
    # matches no endpoint at all. With it None there is no tenancy and every
    # active subscriber matches, which is correct for a single-tenant
    # deployment and is the sort of thing that has to be chosen rather than
    # inherited from a blank column.
    "TENANT_SCOPE_KEY": None,
    # How long one HTTP request may take. Counted against the lease below, so
    # raising it shrinks the room the inner retry has to work in.
    "TIMEOUT_SECONDS": 10.0,
    # The first inner sleep. Doubles from there, capped by the deadline rather
    # than by a separate ceiling: the deadline is the real budget and a second
    # limit would only be a way for the two to disagree.
    "INNER_BACKOFF_BASE_SECONDS": 0.5,
    # Slack left inside the lease after the last attempt could finish. Clock
    # skew, connection setup and the substrate's own bookkeeping all land here,
    # and the cost of being wrong is a duplicate delivery.
    "LEASE_MARGIN_SECONDS": 2.0,
    # A customer's endpoint answering with a redirect has been misconfigured.
    # Following a couple is a kindness; following a chain is an open proxy.
    "MAX_REDIRECTS": 2,
    # The lease the delivery receiver claims, and the budget the inner retry is
    # bounded by. One setting rather than two, because the receiver's lease and
    # the retry's deadline are the same quantity seen from two sides, and two
    # numbers is two ways for them to disagree.
    "DELIVERY_LEASE_SECONDS": 60,
}


def setting(key: str) -> Any:
    """One configured value, falling back to the default.

    ``DEFAULTS[key]`` rather than ``.get(key)``: an unknown key is a typo in
    this package, and a KeyError here beats a None that travels.
    """
    configured = getattr(settings, SETTINGS_NAME, {})
    return configured.get(key, DEFAULTS[key])
