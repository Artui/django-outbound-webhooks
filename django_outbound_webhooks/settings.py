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
}


def setting(key: str) -> Any:
    """One configured value, falling back to the default.

    ``DEFAULTS[key]`` rather than ``.get(key)``: an unknown key is a typo in
    this package, and a KeyError here beats a None that travels.
    """
    configured = getattr(settings, SETTINGS_NAME, {})
    return configured.get(key, DEFAULTS[key])
