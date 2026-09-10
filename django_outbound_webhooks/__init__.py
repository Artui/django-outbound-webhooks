"""Outbound webhooks for Django, delivered as a durable receiver."""

from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for
from django_outbound_webhooks.endpoints.pinned_format import pinned_format
from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint
from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats
from django_outbound_webhooks.signing.sign_request import sign_request
from django_outbound_webhooks.signing.signing_secrets import signing_secrets
from django_outbound_webhooks.types.format_id import FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody
from django_outbound_webhooks.version import __version__

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

__all__ = [
    "BodyFormat",
    "EnvelopeV1",
    "FormatId",
    "FormatRegistry",
    "RenderedBody",
    "__version__",
    "endpoints_for",
    "formats",
    "pinned_format",
    "register_endpoint",
    "sign_request",
    "signing_secrets",
]
