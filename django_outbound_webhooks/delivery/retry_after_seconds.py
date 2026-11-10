from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

#: Statuses whose ``Retry-After`` this package honours: rate limited, and
#: temporarily unavailable. The header means something on a redirect too, but a
#: redirect reaching here has already exhausted the redirect budget, and on any
#: other status it is not a promise the endpoint has made.
HONOURED_STATUSES = frozenset({429, 503})

_DELAY_SECONDS = re.compile(r"[0-9]+")


def retry_after_seconds(value: str | None, *, now: datetime) -> float | None:
    """How long the endpoint asked to be left alone, or None if it did not say."""
    if value is None:
        return None
    text = value.strip()
    if _DELAY_SECONDS.fullmatch(text):
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - now).total_seconds())
