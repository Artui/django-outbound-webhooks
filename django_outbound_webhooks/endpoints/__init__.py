"""The customer-owned endpoint registry, and who an event is owed to.

``validate_webhook_url`` is deliberately absent, for the same reason as its twin
in ``signing``: it is referenced by a model field, so its dotted path is frozen
in the migration, and re-exporting it here would shadow the submodule that path
names. Import it from
``django_outbound_webhooks.endpoints.validate_webhook_url``.
"""

from django_outbound_webhooks.endpoints.endpoints_for import endpoints_for
from django_outbound_webhooks.endpoints.pinned_format import pinned_format
from django_outbound_webhooks.endpoints.register_endpoint import register_endpoint

__all__ = ["endpoints_for", "pinned_format", "register_endpoint"]
