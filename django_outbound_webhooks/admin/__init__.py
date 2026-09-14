"""The admin surface: the registry, the log, replay and per-endpoint health.

Re-exports, unlike the other subpackages here, and for a reason that has nothing
to do with taste: Django's admin autodiscovery imports ``<app>.admin`` and
expects the registrations to have happened by the time that import returns. A
docstring-only ``__init__`` would leave both ModelAdmins unregistered, silently,
with the app installed and the pages simply absent.
"""

from django_outbound_webhooks.admin.delivery_attempt_admin import DeliveryAttemptAdmin
from django_outbound_webhooks.admin.endpoint_admin import EndpointAdmin

__all__ = ["DeliveryAttemptAdmin", "EndpointAdmin"]
