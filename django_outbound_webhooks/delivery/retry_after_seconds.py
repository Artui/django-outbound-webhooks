"""Read an endpoint's ``Retry-After`` header as a number of seconds."""

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
    """How long the endpoint asked to be left alone, or None if it did not say.

    Both forms the header takes: a whole number of seconds, or an HTTP date. A
    date already in the past means "now" rather than a negative delay. Anything
    else is None, which leaves the ordinary retry policy in charge - a header
    that cannot be read is not an instruction.

    Digits are matched as ASCII. ``str.isdigit`` also accepts characters such as
    superscripts, which ``int`` then refuses, so the obvious check would turn a
    malformed header into an exception inside a delivery.
    """
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
        # The obsolete "-0000" zone parses naive and means UTC.
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - now).total_seconds())
