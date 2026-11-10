from __future__ import annotations

from typing import Any

from django.core.checks import Warning

from django_outbound_webhooks.formats.format_registry import formats
from django_outbound_webhooks.settings import setting


def check_default_format_is_published(app_configs: Any, **kwargs: Any) -> list[Warning]:
    """Warn when the format new endpoints would pin does not exist."""
    default = setting("DEFAULT_FORMAT")
    families = sorted({identity.name for identity in formats.published()})
    if default in families:
        return []
    return [
        Warning(
            f"DEFAULT_FORMAT is {default!r}, which no published body format uses as its "
            f"family name, so registering an endpoint without naming a format will fail. "
            f"Published: {', '.join(families) or 'nothing'}.",
            hint=(
                "Set DJANGO_OUTBOUND_WEBHOOKS['DEFAULT_FORMAT'] to a published family, or "
                "publish the one it names. 'cloudevents' in particular is published only "
                "when DJANGO_OUTBOUND_WEBHOOKS['CLOUDEVENTS_SOURCE'] names the system these "
                "events come from."
            ),
            id="django_outbound_webhooks.W002",
        )
    ]
