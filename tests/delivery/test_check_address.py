"""Refusing an address a webhook must not reach."""

from __future__ import annotations

import pytest

from django_outbound_webhooks.delivery.check_address import check_address
from django_outbound_webhooks.delivery.unsafe_destination import UnsafeDestination


@pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700::1111"])
def test_a_public_address_is_allowed(address: str) -> None:
    check_address(address)


@pytest.mark.parametrize(
    ("address", "why"),
    [
        ("169.254.169.254", "link-local"),
        ("127.0.0.1", "loopback"),
        ("10.0.0.1", "private"),
        ("172.16.0.1", "private"),
        ("192.168.1.1", "private"),
        ("0.0.0.0", "unspecified"),
        ("224.0.0.1", "multicast"),
        ("240.0.0.1", "reserved"),
        ("100.64.0.1", "carrier-grade NAT"),
        ("::1", "loopback"),
        ("fd00::1", "private"),
        ("fe80::1", "link-local"),
    ],
)
def test_everything_off_the_public_internet_is_refused(address: str, why: str) -> None:
    with pytest.raises(UnsafeDestination, match=why):
        check_address(address)


def test_carrier_grade_nat_needs_its_own_check() -> None:
    """The one `is_private` does not catch, which is why it is written out.

    Measured rather than assumed: across every flag Python exposes,
    100.64.0.0/10 is not private, not reserved and not anything else. It is
    routable inside a provider's network and unreachable from the public
    internet, which is exactly the shape of a destination worth reaching for.
    """
    import ipaddress

    assert not ipaddress.ip_address("100.64.0.1").is_private
    with pytest.raises(UnsafeDestination, match="carrier-grade NAT"):
        check_address("100.64.0.1")


def test_multicast_needs_its_own_check_too() -> None:
    import ipaddress

    assert not ipaddress.ip_address("224.0.0.1").is_private
    with pytest.raises(UnsafeDestination, match="multicast"):
        check_address("224.0.0.1")


def test_the_refusal_names_every_reason_it_matched() -> None:
    # ::1 is loopback, private and reserved at once. An operator reading one
    # reason would fix that one and be refused again.
    with pytest.raises(UnsafeDestination) as raised:
        check_address("::1")
    assert "loopback" in str(raised.value) and "reserved" in str(raised.value)


class TestWithPrivateAddressesAllowed:
    @pytest.fixture(autouse=True)
    def _allowed(self, settings: object) -> None:
        settings.DJANGO_OUTBOUND_WEBHOOKS = {"ALLOW_PRIVATE_ADDRESSES": True}

    @pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "192.168.1.1", "::1"])
    def test_a_developer_can_reach_their_own_machine(self, address: str) -> None:
        check_address(address)

    @pytest.mark.parametrize(
        ("address", "why"),
        [
            ("169.254.169.254", "link-local"),
            ("fe80::1", "link-local"),
            ("224.0.0.1", "multicast"),
            ("100.64.0.1", "carrier-grade NAT"),
            ("0.0.0.0", "unspecified"),
        ],
    )
    def test_the_hatch_does_not_open_the_dangerous_ones(self, address: str, why: str) -> None:
        # "Let me reach localhost" is never a request to reach the metadata
        # service. One flag granting both would put the worst outcome this
        # package has one setting away.
        with pytest.raises(UnsafeDestination, match=why):
            check_address(address)
