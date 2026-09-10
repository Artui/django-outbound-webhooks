"""One event type an endpoint has asked for."""

from __future__ import annotations

from django.db import models


class Subscription(models.Model):
    """The link between an endpoint and one event name.

    A row per subscription rather than a list on the endpoint. Two reasons, and
    the second is the one that decided it.

    It keeps "which endpoints want this event" an indexed lookup instead of a
    scan over a JSON column, and it keeps that lookup the same statement on
    every backend rather than one that depends on how the database implements
    JSON containment.

    And it is the shape the question grows into. The incumbent's open issues ask
    for topics that are not model names and for subscriptions that can be
    narrowed, so the thing an endpoint subscribes to is going to acquire fields.
    A list of strings has nowhere to put them.
    """

    # Django creates endpoint_id at runtime -- Field.contribute_to_class installs
    # a deferred-attribute descriptor -- and ty has no Django support, so nothing
    # static can see it. The annotation supplies the type. django-domain-events
    # reached the same fix independently, on DeliveryRecord.event_id.
    #
    # Tracked as astral-sh/ty#1018, milestone ty-1.1, implementation still open.
    # Both annotations are removable one day by a ty release, not by anything in
    # either repo.
    #
    # Four dead ends, all measured 2026-09-10. django-stubs is neither cause nor
    # cure -- removing it entirely gives a byte-identical diagnostic, because
    # <fk>_id comes from the mypy plugin shipped inside it and this family runs
    # no mypy. django-types fails the same way. No ty version helps; the latest
    # release errors. No config reaches it; a project with no ty settings at all
    # errors identically. Nor does the declaration style: a class reference, the
    # string reference below, a OneToOneField and even self.id all fail.
    #
    # Preferred over suppressing the rule, which also works: only the annotation
    # supplies a real type, so self.endpoint_id.upper() is still caught.
    #
    # Strictly the value is int | None, being None on an unsaved instance. int is
    # what the django-stubs plugin synthesises for a non-nullable key, and
    # matching that is the more useful simplification.
    endpoint_id: int

    endpoint = models.ForeignKey(
        "django_outbound_webhooks.Endpoint",
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    event_name = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["endpoint", "event_name"],
                name="unique_subscription_per_endpoint",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_name} -> {self.endpoint_id}"
