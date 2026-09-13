"""System checks for wiring that fails silently."""

from __future__ import annotations

from typing import Any

from django.core.checks import Warning, register


@register()
def check_every_event_has_a_fan_out_receiver(app_configs: Any, **kwargs: Any) -> list[Warning]:
    """Warn about a declared event no endpoint can ever receive.

    The fan-out is registered by walking the event registry from
    ``AppConfig.ready()``, because the substrate has no wildcard receiver. That
    makes it sensitive to app load order, and the failure is the quiet kind:
    nothing raises, no endpoint is ever offered the event, and a customer who
    subscribed simply sees nothing.

    The ordering rule is narrower than it first looks, which is worth stating
    because the obvious reading is wrong. The substrate autodiscovers every
    app's ``events.py`` from **its own** ``ready()``, so the registry is complete
    the moment that app finishes -- and this package only has to come after
    *that* one, not after every app that declares an event.

    A system check is still the right shape, because it runs once every app is
    ready, which is the only moment the question has a correct answer.
    """
    from django_domain_events import registry

    from django_outbound_webhooks.delivery.register_fan_out import KEY_PREFIX
    from django_outbound_webhooks.delivery.webhook_delivery_due import WebhookDeliveryDue

    covered = {
        entry.key.removeprefix(f"{KEY_PREFIX}.")
        for entry in registry.receivers()
        if entry.key.startswith(f"{KEY_PREFIX}.")
    }
    missing = sorted(
        entry.name
        for entry in registry.events()
        if entry.event_class is not WebhookDeliveryDue and entry.name not in covered
    )
    if not missing:
        return []
    return [
        Warning(
            "Some declared events have no outbound-webhooks fan-out receiver, so no "
            "endpoint can ever be sent them: " + ", ".join(missing) + ".",
            hint=(
                "The fan-out is wired in AppConfig.ready() by walking the event registry, "
                "which django_domain_events fills from its own ready() by autodiscovering "
                "every app's events.py. List django_outbound_webhooks after "
                "django_domain_events in INSTALLED_APPS."
            ),
            id="django_outbound_webhooks.W001",
        )
    ]


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
