"""System checks for wiring that fails silently."""

from __future__ import annotations

from typing import Any

from django.core.checks import Warning, register


@register()
def check_default_format_is_published(app_configs: Any, **kwargs: Any) -> list[Warning]:
    """Warn when the format new endpoints would pin does not exist.

    ``DEFAULT_FORMAT`` is read at registration, not at startup, so a value
    naming nothing sits quietly until the first customer registers an endpoint
    and then raises there -- in a request, on their side of the product, for a
    configuration mistake made on ours.

    The likeliest way to reach it is not a typo. ``cloudevents`` is published
    only when ``CLOUDEVENTS_SOURCE`` is set, so a deployment that names it as
    the default and forgets the source has a default that is spelled correctly
    and does not exist. The hint says so rather than describing it as a typo,
    because the reader is probably looking straight at the name they meant.

    A ``Warning`` rather than an ``Error``: nothing already registered is
    affected -- an endpoint pins its own format and keeps delivering -- so this
    must not be allowed to stop ``migrate`` on a deployment whose existing
    customers are fine.
    """
    from django_outbound_webhooks.formats.format_registry import formats
    from django_outbound_webhooks.settings import setting

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
