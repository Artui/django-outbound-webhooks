"""The narrowing a single-delivery replay hands the targets callable."""

from __future__ import annotations

from django_outbound_webhooks.delivery.replay_target import replay_target


def test_nothing_is_being_replayed_by_default() -> None:
    """Unset outside a replay, so a first delivery is matched against every
    subscribed endpoint. The behaviour it narrows is tested beside
    delivery_targets and replay_delivery."""
    assert replay_target.get() is None
