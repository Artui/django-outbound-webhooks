"""Outbound webhooks for Django, delivered as a durable receiver."""

import importlib

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats
from django_outbound_webhooks.signing.sign_request import sign_request
from django_outbound_webhooks.types.format_id import FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody
from django_outbound_webhooks.version import __version__

# The names below are served lazily, on first attribute access, rather than
# imported here. Each one reaches the model layer when its module is imported,
# and Django imports this package while it is still loading apps, before models
# may be imported. Importing them eagerly here made the package unimportable
# with AppRegistryNotReady. A consumer sees the same names: `from
# django_outbound_webhooks import register_endpoint` resolves through the
# __getattr__ below, and the static types for them come from __init__.pyi.
# Adding one of them back as a plain import is what breaks the package.
_LAZY_EXPORTS: dict[str, str] = {
    "ReplayRefused": "django_outbound_webhooks.operations.replay_delivery",
    "endpoints_for": "django_outbound_webhooks.endpoints.endpoints_for",
    "pinned_format": "django_outbound_webhooks.endpoints.pinned_format",
    "reactivate_endpoint": "django_outbound_webhooks.operations.reactivate_endpoint",
    "register_endpoint": "django_outbound_webhooks.endpoints.register_endpoint",
    "replay_delivery": "django_outbound_webhooks.operations.replay_delivery",
    "rotate_secret": "django_outbound_webhooks.operations.rotate_secret",
    "signing_secrets": "django_outbound_webhooks.signing.signing_secrets",
}

# The two field validators are deliberately NOT re-exported, here or from their
# own subpackages. Django writes a field's validators into the migration as a
# dotted path, and one-symbol-per-file means a module carries the name of the
# symbol it exports -- so re-exporting one makes the package attribute shadow
# the submodule, the migration's path becomes an attribute lookup on a function,
# and no migration in the app can run. Import them from their leaf modules:
#
#     from django_outbound_webhooks.endpoints.validate_webhook_url import ...
#     from django_outbound_webhooks.signing.validate_signing_secret import ...
#
# The same applies to anything else a migration serialises by path -- a
# `default=` callable, an `upload_to=`, a `through=`.
#
# This package's event classes are not re-exported either, for an unrelated reason with
# the same shape: `@event` resolves its name through the app registry, so
# importing one before the apps are loaded raises AppRegistryNotReady -- and
# this module is imported by Django itself, early, on the way to loading the app.
# A re-export here would make the package unimportable. Import them by leaf path,
# which is also where a receiver declaring itself against one is written:
#
#     from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled

__all__ = [
    "BodyFormat",
    "CloudEventsV1",
    "EnvelopeV1",
    "FormatId",
    "FormatRegistry",
    "RenderedBody",
    "ReplayRefused",
    "__version__",
    "endpoints_for",
    "formats",
    "pinned_format",
    "reactivate_endpoint",
    "register_endpoint",
    "replay_delivery",
    "rotate_secret",
    "sign_request",
    "signing_secrets",
]


def __getattr__(name: str) -> object:
    """Resolve a lazily exported name from its leaf module, and cache the result.

    PEP 562 hook: runs only for names not already bound on this module, so the
    first access imports the leaf and every later access is a plain lookup.
    """
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List every public name, lazy ones included, so tab completion sees them."""
    return sorted(set(globals()) | set(__all__))
