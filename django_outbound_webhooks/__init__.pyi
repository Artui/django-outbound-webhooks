"""Static declarations for the package root.

The root serves some names lazily through a module-level __getattr__, so at
runtime they are resolved on first access rather than bound on import. A type
checker cannot see through that hook, and without this stub every such name
would be Any to a consumer. Each name below is re-exported from the module that
defines it, which is the same object the lazy hook returns.

Every name here must match __all__ in __init__.py, and every lazily served name
must appear in _LAZY_EXPORTS there. tests/test_root_exports.py checks both.
"""

from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for as endpoints_for
from django_outbound_webhooks.endpoints.pinned_format import pinned_format as pinned_format
from django_outbound_webhooks.endpoints.register_endpoint import (
    register_endpoint as register_endpoint,
)
from django_outbound_webhooks.formats.body_format import BodyFormat as BodyFormat
from django_outbound_webhooks.formats.cloud_events_v1 import CloudEventsV1 as CloudEventsV1
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1 as EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry as FormatRegistry
from django_outbound_webhooks.formats.format_registry import formats as formats
from django_outbound_webhooks.operations.reactivate_endpoint import (
    reactivate_endpoint as reactivate_endpoint,
)
from django_outbound_webhooks.operations.replay_delivery import ReplayRefused as ReplayRefused
from django_outbound_webhooks.operations.replay_delivery import replay_delivery as replay_delivery
from django_outbound_webhooks.operations.rotate_secret import rotate_secret as rotate_secret
from django_outbound_webhooks.signing.sign_request import sign_request as sign_request
from django_outbound_webhooks.signing.signing_secrets import signing_secrets as signing_secrets
from django_outbound_webhooks.types.format_id import FormatId as FormatId
from django_outbound_webhooks.types.rendered_body import RenderedBody as RenderedBody
from django_outbound_webhooks.version import __version__ as __version__

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
