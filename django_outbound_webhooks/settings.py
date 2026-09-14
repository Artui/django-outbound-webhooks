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
    # The CloudEvents `source` attribute: which system produced these events.
    # None means the CloudEvents format is not published at all, and that is the
    # honest default rather than a timid one. The specification requires a
    # non-empty source, there is nothing in a Django project to derive one from
    # that would mean anything to a consumer, and an invented value would be the
    # unnamed default this package refuses one level down -- with the added
    # unpleasantness that it would be *signed*. So: set this and the format is
    # published; leave it and `cloudevents` is not a family an endpoint can pin,
    # which register_endpoint refuses by naming the families that do exist.
    "CLOUDEVENTS_SOURCE": None,
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
    # Development escape hatch, and deliberately a partial one. Turning it on
    # allows private and loopback addresses, so a developer can deliver to a
    # tunnel or a container on their own machine. It does not allow link-local,
    # which is where the cloud metadata endpoint lives, nor multicast, reserved,
    # unspecified or carrier-grade NAT space: "let me reach localhost" is never
    # a request to reach any of those, and a single flag that granted all of it
    # would be one setting away from the worst outcome this package has.
    "ALLOW_PRIVATE_ADDRESSES": False,
    # How much of an endpoint's response body the log keeps. Enough to read an
    # error page's first paragraph, not enough for a customer's HTML to become
    # the largest table in the database.
    "LOG_BODY_CHARS": 1000,
}


def setting(key: str) -> Any:
    """One configured value, falling back to the default.

    ``DEFAULTS[key]`` rather than ``.get(key)``: an unknown key is a typo in
    this package, and a KeyError here beats a None that travels.
    """
    configured = getattr(settings, SETTINGS_NAME, {})
    return configured.get(key, DEFAULTS[key])
