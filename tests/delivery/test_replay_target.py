from __future__ import annotations

from django_outbound_webhooks.delivery.replay_target import replay_target


def test_nothing_is_being_replayed_by_default() -> None:
    """Unset outside a replay, so a first delivery is matched against every subscribed endpoint."""
    assert replay_target.get() is None
