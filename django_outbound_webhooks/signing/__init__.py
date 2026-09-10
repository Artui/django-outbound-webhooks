"""Signing a delivery to the Standard Webhooks specification.

``validate_signing_secret`` is deliberately absent from ``__all__`` and from the
imports above. It is referenced by a model field, so Django writes its dotted
path into the migration, and re-exporting a symbol whose module carries the same
name makes this package's attribute shadow that submodule -- at which point the
migration's path resolves to a function and no migration in the app can run.
Import it from ``django_outbound_webhooks.signing.validate_signing_secret``.
"""

from django_outbound_webhooks.signing.sign_request import sign_request
from django_outbound_webhooks.signing.signing_secrets import signing_secrets

__all__ = ["sign_request", "signing_secrets"]
