"""Body formats: what a customer's endpoint receives, and which version of it."""

from django_outbound_webhooks.formats.body_format import BodyFormat
from django_outbound_webhooks.formats.envelope_v1 import EnvelopeV1
from django_outbound_webhooks.formats.format_registry import FormatRegistry, formats

__all__ = ["BodyFormat", "EnvelopeV1", "FormatRegistry", "formats"]
