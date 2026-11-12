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

## How delivery works

One durable receiver, declared for every event. When your code fires an event,
the endpoints subscribed to it - within its tenant, when the deployment has
tenants - are looked up in the same transaction, and each gets a delivery row of
its own, carrying the format it is pinned to and a `webhook-id` minted for it. So
every endpoint has its own attempt count, backoff, dead-letter and replay, and a
rotted endpoint cannot drag the others through its retries. An event nobody
subscribes to writes no delivery row at all.

With `TENANT_SCOPE_KEY` set, an event whose scope has no value under that key
reaches no endpoint, and no delivery row is written for it, so a missing tenant
fails closed rather than reaching every subscriber. In that deployment an
endpoint without a tenant is refused at registration, for the same reason.
Without the key, every active subscriber to the event is owed it.

An endpoint answering `429` or `503` with `Retry-After` is taken at its word:
that delivery stops retrying inside its lease and its next attempt is scheduled
for the time the endpoint named, which still counts against the delivery's
attempt budget.

Within one delivery, a `408`, `429` or `5xx` answer is retried, and any other
answer that is not a `2xx` ends that delivery's requests at once. The delivery
itself is still retried on the substrate's schedule, so a `410` or a `400` uses
the whole budget of five attempts before it is dead-lettered, and counts toward
auto-disable like any other dead delivery.

A request the address check refuses is not recorded as an attempt. Its delivery
is retried on the substrate's schedule and dead-lettered like any other, and the
reason is on the substrate's delivery record, not in the attempt log.

Two things follow from where the lookup runs. It is **one indexed query in the
transaction that fires the event**, on every event your project fires. And it
does not depend on the order of `INSTALLED_APPS`: the receiver is matched when an
event is fired, so an event declared by an app listed after this one is delivered
like any other.

## Where deliveries go

Every request goes to an address the package has checked, and that check is the
policy. The check runs when a request is sent, not when the endpoint is
registered: registration only requires an `http` or `https` URL. A destination
is refused if it resolves to link-local, multicast, unspecified, reserved or
carrier-grade NAT space, and no setting changes that. Private and loopback space
are refused too, unless `ALLOW_PRIVATE_ADDRESSES` is set, which is for
development. An IPv6 address that embeds an IPv4 address (6to4, IPv4-mapped) is
judged by that IPv4 address too, so `2002:a9fe:a9fe::1` is refused as the link-local
metadata address it carries.

A hostname is resolved once for each request, every address it returns is
checked, and the connection is made to the address that was checked. A DNS
answer that changes between the check and the connection therefore cannot move
the request. A literal IP in the URL is checked without a lookup. Redirects are
followed up to `MAX_REDIRECTS`, and each hop is checked the same way. A `307` or
`308` redirect re-sends the signed body and the `webhook-` headers to its
target, so a redirect is a second place the payload can go.

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

`render()` returns UTF-8 bytes, because the signature is computed over the body
as text. The registry checks the method's keywords when a format is registered,
but not the encoding: a body that is not UTF-8 is refused when a delivery is
sent, and that delivery is retried like any other failure.

## Signing

Each request carries `webhook-id`, `webhook-timestamp` and `webhook-signature`,
as the Standard Webhooks specification defines them, and the signature covers
the body as text. The secret is the base64 string you registered, with or
without its `whsec_` prefix. This package signs but does not verify: a customer
verifies with a Standard Webhooks library, using that secret. During a rotation
the header carries one signature per secret still in its overlap window, and a
receiver accepts the request if any of them verifies.

Every retry of a delivery sends the same body under the same `webhook-id`, so a
receiver can deduplicate on that header. `webhook-timestamp` is taken fresh for
each attempt, so a receiver should check it against its own tolerance window,
not against the first attempt.

## Operations

```python
from django_outbound_webhooks import reactivate_endpoint, replay_delivery, rotate_secret

replay_delivery(message_id="018f...")  # a new delivery of a logged one
rotate_secret(endpoint, new_secret=secret)  # both secrets sign until the window closes
reactivate_endpoint(endpoint)  # back on, and the failure count cleared
```

Importing the package does not load the models, but these names and the
modules that define them do, so they can only be imported once Django's app
registry is ready. Import them from a view, a task or a signal handler, not at
the top of an `apps.py`, a package `__init__.py`, or a settings module.

A replay is a **new** delivery: a new `webhook-id` (a receiver deduplicates on
that one), the endpoint's current format and secrets, and its own delivery row,
attempt budget and log rows. It refuses rather than firing something that cannot
arrive - an unlogged message id, a deleted endpoint, an inactive one, an event
retention has pruned, or an event no longer declared.

`replay_delivery` returns once the new delivery is recorded, not once it is
sent. The send happens later, when the substrate's relay claims the row. Its
outcome is in the attempt log under the returned `webhook-id`.

Replaying the whole *event* with django-domain-events' own `replay_events` is a
different operation: it delivers the event again to every endpoint subscribed
**now**, each under a new `webhook-id`.

A rotation overlaps. The specification carries several signatures in one header
and a receiver accepts the delivery if any verifies, so the customer deploys the
new secret on their own schedule and nothing is dropped in between.

The first dead delivery of an incident fires `EndpointFailing`, and the delivery
that ends it fires `EndpointRecovered` - once each, however much traffic the
incident spans, and even with auto-disable turned off, where the warning is the
only signal there is. `EndpointFailing` carries the threshold that will switch
the endpoint off, so a notification can say when.

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

None of the three is ever delivered to a customer endpoint: whoever subscribed
would be told about somebody else's integration, over their own webhook.

A delivery still queued when its endpoint is switched off or deleted is dropped
when it next runs. Nothing is sent and no attempt row is written, so it does not
appear in the log and cannot be replayed by its `webhook-id`.

## Settings

Each delivery has `DELIVERY_LEASE_SECONDS` to finish its requests. The package
retries a failed request until the delivery has used the lease less
`TIMEOUT_SECONDS` and `LEASE_MARGIN_SECONDS`, and no further request is started
after that. Raise the lease or lower the timeout if a lease cannot hold one
request and the margin: otherwise every delivery raises a `ValueError` when it is
sent. The other keys are described where their behaviour is: `TENANT_SCOPE_KEY`
under "How delivery works", `ALLOW_PRIVATE_ADDRESSES` and `MAX_REDIRECTS` under
"Where deliveries go", and `LOG_BODY_CHARS` under "Admin".

## Admin

Add `django.contrib.admin` and the endpoints and the delivery log are there: per-
endpoint health in the unit that means something, a link from each endpoint to
its own attempts, replay as an action on the log, and reactivation as an action
on the registry.

Each log row is one attempt at the endpoint's URL. It keeps that URL as it was
then, query string included, a SHA-256 and the length of the request body, and
the first `LOG_BODY_CHARS` of the response body or of the transport error. The
body itself is not kept. Deleting an endpoint keeps its rows and clears only
their link to it, so a row can name a URL the registry no longer holds.

**No signing secret is ever rendered**, and endpoints cannot be created there -
`register_endpoint` is where the rules live. `tenant` and the pinned format are
read-only: the first decides whose payload reaches whose URL, and the other two
are the shape the customer wrote code against.

Both actions declare their permission, because Django offers an action without
one to anyone who can open the changelist. Replay is gated on the **endpoint's**
change permission rather than the log's, so a support user can be given the log
to read without being able to make deliveries happen.

## Status

Released and in use, pre-1.0. Shipped: the registry, signing, delivery with a
lease-bounded retry, the request-forgery policy, the delivery log, two body
formats, the operations above and the admin surface. What 1.0 waits on is time
in production rather than a feature.
