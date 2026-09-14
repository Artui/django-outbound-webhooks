"""One customer-registered destination for webhook deliveries."""

from __future__ import annotations

from django.db import models

from django_outbound_webhooks.endpoints.validate_webhook_url import validate_webhook_url
from django_outbound_webhooks.signing.validate_signing_secret import validate_signing_secret


class Endpoint(models.Model):
    """Where one customer wants deliveries, in the shape they integrated against.

    A row and nothing else. What the columns mean lives beside the code that
    acts on them -- ``pinned_format``, ``signing_secrets``, ``endpoints_for`` --
    and the supported way to create one is ``register_endpoint``, which is where
    the cross-field rules and the format pinning live.

    The validators below are declarations rather than logic, and they are on the
    fields so that every path that runs ``full_clean`` gets them: a form, the
    admin, a serializer, and ``register_endpoint``.
    """

    #: What the customer calls this endpoint. Required, because a customer with
    #: several endpoints has no other way to tell them apart: a URL is long, a
    #: primary key is meaningless to them, and both appear in the delivery log
    #: and in every support conversation about a failing integration.
    #:
    #: Not unique. Two endpoints called "production" are confusing rather than
    #: harmful, and a uniqueness constraint on a field a customer types is a
    #: refusal they cannot act on when the clash is with a row they cannot see.
    name = models.CharField(max_length=100)

    url = models.URLField(max_length=2000, validators=[validate_webhook_url])
    secret = models.CharField(
        max_length=255,
        validators=[validate_signing_secret],
        help_text="Base64, optionally with the whsec_ prefix the specification uses.",
    )

    #: Pinned at registration and then frozen. The endpoint stops following the
    #: latest version the moment it is created, because the bytes it receives
    #: are what its owner wrote code against.
    format_name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()

    #: The customer this endpoint belongs to, matched against the event's scope.
    #: Blank only where the deployment has no tenancy at all; see
    #: ``TENANT_SCOPE_KEY``.
    tenant = models.CharField(max_length=255, blank=True, db_index=True)

    #: The secret this endpoint signed with before the last rotation, and the
    #: moment it stops being offered. Two columns rather than one because a
    #: rotation without an overlap is a coordinated cutover, which is the thing
    #: the specification's multi-signature header exists to avoid: the customer
    #: deploys their new secret whenever they like, and both verify until the
    #: window closes. ``rotate_secret`` is the only supported writer of either.
    previous_secret = models.CharField(max_length=255, blank=True)
    previous_secret_expires_at = models.DateTimeField(null=True, blank=True)

    #: Consecutive deliveries the substrate gave up on, counting the *outer*
    #: tier: one dead delivery is one webhook that exhausted its whole attempt
    #: budget, not one failed HTTP request. Reset by the first delivery that
    #: succeeds. The name says the tier because an auto-disable threshold
    #: counted in requests would fire orders of magnitude sooner than the same
    #: number counted in deliveries.
    consecutive_dead_deliveries = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    #: When this package switched the endpoint off, and null when it did not.
    #: An operator deactivating an endpoint by hand leaves this null, so the two
    #: reasons an endpoint is inactive stay distinguishable -- which matters,
    #: because only one of them should be undone by ``reactivate_endpoint``
    #: without asking anybody.
    disabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "tenant"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"
