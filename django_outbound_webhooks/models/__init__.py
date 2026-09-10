"""The endpoint registry: rows a customer owns."""

from django_outbound_webhooks.models.endpoint import Endpoint
from django_outbound_webhooks.models.subscription import Subscription

__all__ = ["Endpoint", "Subscription"]
