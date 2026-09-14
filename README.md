# django-outbound-webhooks

[![CI](https://github.com/Artui/django-outbound-webhooks/workflows/tests/badge.svg)](https://github.com/Artui/django-outbound-webhooks/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Django versions](https://img.shields.io/pypi/djversions/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Docs](https://img.shields.io/badge/docs-artui.github.io-blue.svg)](https://artui.github.io/django-outbound-webhooks/)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Artui/django-outbound-webhooks/gh-pages/coverage.json)](https://github.com/Artui/django-outbound-webhooks/actions/workflows/tests.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/django-outbound-webhooks.svg)](LICENSE)

Outbound webhooks for Django, built on
[django-domain-events](https://github.com/Artui/django-domain-events).

Your customers subscribe to domain events, not to your `post_save` signals. An
endpoint is a row a customer owns: a URL, a secret, the events it wants and the
body format it was integrated against. Delivery is a durable receiver, so
retry, backoff, dead-lettering and replay are inherited rather than rebuilt.

## Install

```bash
pip install django-outbound-webhooks
```

## Body formats

A customer's endpoint is pinned to one published format *version* when it
registers, and that version is frozen: changing what it renders would change
what an already-integrated consumer receives, under a signature that still
verifies. A change is a new version.

| Family | Content type | Shape |
| --- | --- | --- |
| `envelope` | `application/json` | `id`, `type`, `timestamp`, and the payload under `data` |
| `cloudevents` | `application/cloudevents+json; charset=UTF-8` | CloudEvents 1.0, structured mode |

```python
register_endpoint(
    name="Acme production",
    url="https://acme.example/hooks/orders",
    secret=secret,
    event_names=["shop.OrderPlaced"],
    # Both optional. Without format_name, DEFAULT_FORMAT decides; without
    # format_version, the latest is pinned and that number is written down.
    format_name="cloudevents",
)
```

`cloudevents` is published only when the deployment says which system produced
the events, because the specification requires a non-empty `source` and an
invented one would be signed into every body:

```python
DJANGO_OUTBOUND_WEBHOOKS = {"CLOUDEVENTS_SOURCE": "https://shop.example/events"}
```

Your own format is an object with a `name`, a `version` and a `render()`, which
you publish from your `AppConfig.ready()`:

```python
from django_outbound_webhooks import formats

formats.register(MyFormat())
```

It does not have to inherit from anything: `BodyFormat` is a `Protocol`. The
registry checks at registration that what you handed it can actually render a
delivery, because a format is published once at startup and called hours later
in another process.

## Operations

```python
from django_outbound_webhooks import reactivate_endpoint, replay_delivery, rotate_secret

replay_delivery(message_id="018f...")  # a new delivery of a logged one
rotate_secret(endpoint, new_secret=secret)  # both secrets sign until the window closes
reactivate_endpoint(endpoint)  # back on, and the failure count cleared
```

A replay is a **new** delivery: a new `webhook-id` (a receiver deduplicates on
that one), the endpoint's current format and secrets, and its own delivery row,
attempt budget and log rows. It refuses rather than firing something that cannot
arrive - a deleted endpoint, an inactive one, an event retention has pruned.

A rotation overlaps. The specification carries several signatures in one header
and a receiver accepts the delivery if any verifies, so the customer deploys the
new secret on their own schedule and nothing is dropped in between.

An endpoint that stops answering is switched off after
`AUTO_DISABLE_AFTER_DEAD_DELIVERIES` consecutive **dead deliveries** - each of
which has already spent a whole attempt budget across processes and hours, so
the default of twenty is an endpoint that is gone rather than one having a bad
afternoon. A delivery that lands resets the count. Somebody has to tell the
customer, so it fires an event you can receive:

```python
from django_domain_events import receiver
from django_outbound_webhooks.operations.endpoint_disabled import EndpointDisabled


@receiver(EndpointDisabled, key="acme.email_the_customer")
def email_the_customer(disabled: EndpointDisabled) -> None: ...
```

## Status

Released and in use, pre-1.0. Shipped: the registry, signing, delivery with a
lease-bounded retry, the request-forgery policy, the delivery log, two body
formats, and the operations above. Not yet: the admin surface.
