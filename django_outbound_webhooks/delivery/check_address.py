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
    """Raise unless this address is somewhere on the public internet."""
    parsed = ipaddress.ip_address(address)

    allow_private = setting("ALLOW_PRIVATE_ADDRESSES")
    never = {
        "link-local": parsed.is_link_local,
        "multicast": parsed.is_multicast,
        "unspecified": parsed.is_unspecified,
        "carrier-grade NAT": parsed in CARRIER_GRADE_NAT,
        "reserved": parsed.is_reserved and not (allow_private and parsed.is_loopback),
    }
    local = {
        "private": parsed.is_private,
        "loopback": parsed.is_loopback,
    }

    matched = dict(never)
    if not allow_private:
        matched.update(local)

    named = sorted(name for name, hit in matched.items() if hit)
    if named:
        raise UnsafeDestination(
            f"{address} is {', '.join(named)}, which a webhook must not be delivered to. "
            f"An endpoint URL is written by a customer, so it reaches whatever they type."
        )
