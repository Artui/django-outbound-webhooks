"""Declared only once ``tests.lateapp`` is installed; nothing else imports it."""

from __future__ import annotations

from dataclasses import dataclass

from django_domain_events import event


@event
@dataclass(frozen=True)
class LateArrival:
    value: int
