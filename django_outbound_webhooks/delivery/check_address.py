"""Refuse an address a webhook must not reach."""

from __future__ import annotations

import ipaddress

from django_outbound_webhooks.delivery.unsafe_destination import UnsafeDestination
from django_outbound_webhooks.settings import setting

#: Carrier-grade NAT, RFC 6598. Checked explicitly because Python does **not**
#: count it as private -- verified 2026-09-10 across the whole range of flags --
#: and it is routable inside a provider's network while being unreachable from
#: the public internet. A customer URL resolving here is either a mistake or an
#: attempt to reach a neighbour.
CARRIER_GRADE_NAT = ipaddress.ip_network("100.64.0.0/10")


def check_address(address: str) -> None:
    """Raise unless this address is somewhere on the public internet.

    ``is_private`` is the obvious single test and it is not enough. It does
    catch the one everybody names -- ``169.254.169.254``, the cloud metadata
    endpoint -- because link-local is private. What it misses is carrier-grade
    NAT, which is not private in Python's classification at all, and multicast,
    which is not either.

    Every category is refused rather than only the famous one, because the
    interesting attacks are the addresses nobody thought to name. Reserved space
    is refused for the same reason: today it routes nowhere, and a package that
    connects to whatever a stranger types should not be the thing that discovers
    it started routing somewhere.

    ``ALLOW_PRIVATE_ADDRESSES`` relaxes exactly two of these categories, private
    and loopback, so a developer can deliver to a container or a tunnel on their
    own machine. It deliberately does not relax link-local, which is where the
    metadata endpoint lives, nor any of the rest: "let me reach localhost" is
    never a request to reach the metadata service, and one flag granting both
    would put the worst outcome this package has one setting away.
    """
    parsed = ipaddress.ip_address(address)

    # Two tiers, because the escape hatch relaxes one of them and must never
    # relax the other. Splitting them by name rather than by a flag comparison
    # is what keeps that readable: everything in `never` stays refused with the
    # hatch wide open.
    never = {
        "link-local": parsed.is_link_local,
        "multicast": parsed.is_multicast,
        "unspecified": parsed.is_unspecified,
        "carrier-grade NAT": parsed in CARRIER_GRADE_NAT,
    }
    # "Somewhere on this machine or this network". `reserved` belongs here
    # rather than above, and the reason is concrete: ``::1`` is loopback,
    # private *and* reserved at once, so leaving reserved in the other tier made
    # the hatch refuse IPv6 loopback while allowing the IPv4 one. It grants
    # nothing extra either, since every reserved range is already private.
    local = {
        "private": parsed.is_private,
        "loopback": parsed.is_loopback,
        "reserved": parsed.is_reserved,
    }

    matched = dict(never)
    if not setting("ALLOW_PRIVATE_ADDRESSES"):
        matched.update(local)

    named = sorted(name for name, hit in matched.items() if hit)
    if named:
        raise UnsafeDestination(
            f"{address} is {', '.join(named)}, which a webhook must not be delivered to. "
            f"An endpoint URL is written by a customer, so it reaches whatever they type."
        )
