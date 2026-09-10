"""Outbound webhooks for Django, delivered as a durable receiver."""

from django_outbound_webhooks.endpoints_for import endpoints_for
from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats
from django_outbound_webhooks.pinned_format import pinned_format
from django_outbound_webhooks.register_endpoint import register_endpoint
from django_outbound_webhooks.sign_request import sign_request
from django_outbound_webhooks.signing_secrets import signing_secrets
from django_outbound_webhooks.types.format_id import FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody
from django_outbound_webhooks.version import __version__

# The two field validators are deliberately NOT re-exported here, and it is not
# an oversight. Django writes a field's validators into the migration as a
# dotted path, and re-exporting a symbol whose module has the same name -- which
# one-symbol-per-file guarantees -- makes the package attribute *shadow the
# submodule*: `django_outbound_webhooks.validate_webhook_url` then resolves to
# the function, so the migration's
# `django_outbound_webhooks.validate_webhook_url.validate_webhook_url` raises
# AttributeError and no migration in the app can run.
#
# Import them from their leaf modules, which is what the migration does:
#     from django_outbound_webhooks.validate_webhook_url import validate_webhook_url
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
