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

## Status

Released and in use, pre-1.0. Shipped: the registry, signing, delivery with a
lease-bounded retry, the request-forgery policy, the delivery log, and two body
formats. Not yet: replay from the log, secret rotation with overlap,
auto-disable on sustained failure, and the admin surface.
