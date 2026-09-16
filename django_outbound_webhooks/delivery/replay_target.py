"""The one delivery a replay is for, while the substrate re-derives targets."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_outbound_webhooks.types.delivery_target import DeliveryTarget

#: Set by ``replay_delivery`` for the duration of one substrate replay, as the
#: event being replayed and the single target it is owed.
#:
#: A replay goes through the substrate's own ``replay_events``, so it gets a
#: delivery row, an attempt budget and a place in the log exactly as a first
#: delivery does. That operation calls the receiver's ``targets`` callable
#: again, and left alone the callable would name every endpoint subscribed now
#: - which is what replaying a whole *event* should do, and not what replaying
#: one logged *delivery* means. This is how the callable learns the narrower
#: question is being asked.
#:
#: Carries the event id as well as the target, and the callable honours it only
#: for that event. A value that outlived its replay would otherwise send every
#: later event to one customer's endpoint, which is the worst failure this
#: package has; tied to one event id, the most a leak could do is repeat the
#: replay it was set for.
replay_target: ContextVar[tuple[int, DeliveryTarget] | None] = ContextVar(
    "django_outbound_webhooks_replay_target", default=None
)
