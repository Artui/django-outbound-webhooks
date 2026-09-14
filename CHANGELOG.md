# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-09-14

The admin surface, which is the last milestone this package's plan queued.

Its entries spent a few hours filed under `## [0.2.0]`, a version already on
PyPI without them: the squash merge that landed them duplicated that heading
rather than conflicting, so nothing failed and the file read as one section with
two `### Added` blocks. Cutting this release is what surfaced it. The section
below now reads exactly as 0.2.0 was published.

### Added
- The admin surface: the endpoint registry, the delivery log, replay and
  per-endpoint health, as two ModelAdmins Django's autodiscovery picks up.
- `EndpointAdmin` shows health in the unit that means something - "3 dead
  deliveries in a row", never a bare number - links each row to its own
  attempts rather than counting them, and offers `reactivate` as an action that
  clears the count with the flag.
- `DeliveryAttemptAdmin` is read-only, renders both attempt numbers as `3.2` so
  the tier each counts stays legible, and offers `replay`. Replay is **once per
  delivery, not once per row**: the log holds a row per HTTP request, so a
  failed delivery is several rows, and replaying per row would send the
  customer one webhook per attempt the original made. A refusal is reported and
  the rest of the selection still goes.

### Security
- **No signing secret is ever rendered.** Both secret columns are excluded from
  the endpoint form rather than made read-only, because a read-only field is
  still displayed: an operator with view access would be reading the credential
  that authenticates every delivery to that customer, and a support screenshot
  would carry it out of the building. Rotation stays a library call, which
  leaves the new secret with the caller rather than on a page.
- **Endpoints cannot be added through the admin.** `register_endpoint` is where
  the cross-field rules and the format pinning live; a row created through a
  form would have no subscriptions, no validated pinning and a secret typed
  into a browser.
- **`tenant`, `format_name` and `format_version` are read-only.** The first is
  the isolation boundary, so editing it in a form moves one customer's endpoint
  to another customer. The other two are the shape its owner wrote code
  against.
- **Both actions declare `permissions=`.** Django offers an action without them
  to anyone who can reach the changelist, which includes view-only staff, and
  `has_change_permission` gates the form rather than the action - so refusing
  there refuses nothing. Replay is gated on the **endpoint's** change
  permission rather than the log's, because a replay mutates nothing in the log
  and what it actually does is send a customer a webhook.

### Fixed
- `scripts/check-changelog` refuses to run with no filenames instead of
  reporting success. It already looks for a duplicated version heading, which is
  exactly the damage this release had to repair - and it found it the moment it
  was handed the file. Every hand-check of it that day had been made without
  one, so the exit code said nothing five times in a row. A guard that passes
  when it was asked nothing is worse than no guard, because somebody reads the
  exit code as evidence.

## [0.2.0] — 2026-09-14

A second body format and the operational surface, released together: both landed
on `main` before either was published, and one release is the honest way to
describe what a consumer installs. The plan queued them as separate milestones,
which is a build order rather than a release schedule - the only numbers that
mean anything to somebody installing this are the ones below.

### Added
- `replay_delivery`, which fires a logged delivery again. A replay is a **new**
  delivery, and everything follows from that: it gets a new `webhook-id`,
  because a receiver deduplicates on that one and replaying under the original
  asks a well-behaved consumer to discard exactly what somebody asked for; it
  re-reads the endpoint's current pinned format and current secrets, because
  those are the integration contract as it stands today; and it goes through
  the substrate, so it has its own delivery row, attempt budget, backoff,
  dead-lettering and log rows. It refuses rather than firing something that
  cannot arrive: an unlogged message id, a deleted endpoint, an inactive one,
  and an event retention has already pruned.
- `rotate_secret`, and the two columns it writes. The specification carries
  several signatures in one header and a receiver accepts the delivery if any
  verifies, which is what lets the two sides move independently: this side
  rotates now, the customer deploys the new secret on their own schedule, and
  nothing is dropped in between. `SECRET_ROTATION_OVERLAP_SECONDS` sets the
  window; passing `overlap_seconds=0` cuts over immediately, which is right for
  exactly one case - a leaked secret - and wrong for every other.
- Auto-disable on sustained failure. `AUTO_DISABLE_AFTER_DEAD_DELIVERIES`
  counts **dead deliveries**, not failed requests: one dead delivery has
  already spent its whole attempt budget across processes and hours, so the
  default of twenty in a row is an endpoint that is gone rather than one having
  a bad afternoon. The same number counted in HTTP requests would fire within
  minutes. A delivery that lands resets the count, which is what makes the
  threshold mean *sustained*; `None` turns the feature off and keeps counting.
- `EndpointDisabled`, fired when that happens. An event rather than a log line
  because somebody has to tell the customer, and every way of doing that -
  email, a ticket, a banner - is code in an app this package has never heard
  of. It is deliberately **not** fanned out to customer endpoints: the endpoint
  most obviously interested has just been switched off, so a customer
  subscribed to it would only ever hear about other people's failures.
- `reactivate_endpoint`, which clears the count along with the flag. An
  endpoint re-enabled with its count still at the threshold is disabled again
  by its very next dead delivery, which looks exactly like the re-enabling
  having silently failed.
- `CloudEventsV1`, a second published body format: one event as a structured-mode
  CloudEvent, content type `application/cloudevents+json; charset=UTF-8`. It is
  the milestone that tests the format seam rather than the one that introduced
  it, and the seam held - the same `render()` call, no new column on the
  endpoint, and `envelope@1` renders the byte-identical fixture it was published
  with.
- `CLOUDEVENTS_SOURCE`. The format is published only when a deployment says
  which system produced its events: the specification requires a non-empty
  `source`, there is nothing in a Django project to derive a meaningful one
  from, and an invented one would be signed into every body. Unset, `cloudevents`
  is not a family an endpoint can pin, so the refusal lands at registration and
  names the families that do exist.
- `django_outbound_webhooks.W002`, for a `DEFAULT_FORMAT` no published format
  uses as its family name. That value is read when an endpoint registers rather
  than at startup, so without the check the first customer to register one meets
  the error instead of the operator. The likeliest way to reach it is not a typo
  but naming `cloudevents` with no source configured, and the hint says so.
- Conformance tests taken from the CloudEvents specification rather than from
  this renderer: the four required attributes, `data` carried as a JSON value
  rather than a stringified one, no invented member, and a content type copied
  from the HTTP binding's own structured-mode example. Every other test here
  compares the format to itself or to its own fixture, which proves agreement
  and not conformance - the distinction the signing tests already make by
  verifying against the Standard Webhooks example.
- `register_built_in_formats`, which publishes both into a registry it is given.
  The argument is what makes the conditional testable: re-running `ready()` to
  reach the unpublished state would also re-register the receivers.

### Changed
- `signing_secrets` now returns the previous secret too while a rotation window
  is open, newest first. It has returned a list since the first release for
  this reason, so no call site changed.
- The endpoint table gains four columns, all of which read correctly on an
  existing row without a backfill: `previous_secret` blank and
  `previous_secret_expires_at` null say "never rotated",
  `consecutive_dead_deliveries` zero says "nothing has failed yet", and
  `disabled_at` null says "we did not switch this off" - which is how an
  endpoint an operator deactivated by hand stays distinguishable from one this
  package disabled.
- The CloudEvents format renders with `ensure_ascii` off, where the envelope
  renders with it on. Both are pinned rather than defaulted, for the same reason
  - the bytes are signed and their hash is recorded - and they differ because
  this one's media type declares `charset=UTF-8`, which is the encoding the
  specification's JSON format uses.

### Fixed
- The package root refuses to re-export either event class, and says why. An
  `@event` resolves its name through the app registry, so importing one before
  the apps are loaded raises `AppRegistryNotReady` - and Django imports this
  package early, on the way to loading the app. A re-export would have made the
  package unimportable, which is a failure that surfaces nowhere near the line
  that caused it.
- The compatibility table in `CLAUDE.md` said the `django-domain-events` floor
  was 0.7.0 and explained why. 0.1.0 raised it to 0.8.0 for the receiver's
  `on_failure` hook and left the table and its reasoning behind, which is the
  form a stale floor claim takes when only the resolver is checked.

## [0.1.0] — 2026-09-11

### Added
- Initial scaffold.

This first release covers both milestones the plan had queued: the registry,
signing, fan-out and delivery, and the delivery log and request-forgery policy
that were planned a release later. They are here together because they were built
together, and holding half of it back to match a milestone number would have
shipped a package that posts to whatever URL a customer types.
- Layout: the package root holds `__init__.py`, `version.py`, `settings.py` and
  `apps.py`, with everything else under a subpackage named for a concern -
  `signing/`, `endpoints/`, `formats/`, `models/`, `types/`.
- Body formats: `BodyFormat` (a `Protocol`, so an operator's own format inherits
  nothing from this package), a `FormatRegistry` keyed by name and version, and
  `EnvelopeV1` as the first published format. An endpoint pins the version it
  was integrated against, so a published version is frozen and a change is a new
  version rather than an edit. Golden fixtures generated by the package's own
  renderer are what enforce that, with `scripts/generate-format-fixtures` checked
  in beside them.
- `FormatId` and `RenderedBody`, the two value carriers the format seam needs.
  A rendered body is bytes plus a content type, because the signature is
  computed over the body and any encoding step between rendering and signing is
  somewhere the signed bytes and the sent bytes can diverge.
- `sign_request`, producing the three Standard Webhooks headers. It takes a
  sequence of secrets rather than one, so signing with an outgoing and an
  incoming secret at once gives the rotation overlap the specification already
  allows for.
- `Endpoint` and `Subscription`: the customer-owned registry. An endpoint carries
  a name its owner chose, its URL, its signing secret, the format version it is
  pinned to and the tenant it belongs to; subscriptions are rows rather than a list on the endpoint, so
  "which endpoints want this event" is an indexed lookup that reads the same on
  every backend.
- `endpoints_for`, which answers that question inside the tenant boundary. With
  `TENANT_SCOPE_KEY` configured, an event carrying no usable value under that key
  matches nothing at all.
- `register_endpoint`, the supported way to add one. It is where the cross-field
  rules and the format pinning live: an unpinned registration pins whatever is
  latest and records that number, and a version that was never published is
  refused at registration rather than at the first delivery.
- `pinned_format`, `signing_secrets`, `validate_webhook_url` and
  `validate_signing_secret`. The models carry fields and a `__str__` and nothing
  else, so everything that interprets a column lives beside the code that acts on
  it. The two validators are declared on their fields, so a form, the admin and a
  serializer all get them.
- `DJANGO_OUTBOUND_WEBHOOKS` settings: `DEFAULT_FORMAT` and `TENANT_SCOPE_KEY`.

- `FormatRegistry.register` checks conformance and refuses at registration: a
  missing attribute, a `render` that is not callable, or a `render` that does not
  accept the keywords a delivery calls it with. Neither the protocol nor
  `isinstance` can make that check, and a format is registered once at startup
  and called hours later in another process.

- Delivery: `send_webhook` posts a rendered, signed body and retries inside the
  lease. `send_once` is one attempt, `classify_response` reads a status as a
  verdict, `retry_policy` builds the tenacity object per delivery, and
  `lease_deadline` holds the arithmetic that keeps it all inside the lease.
  `webhook_client` is the httpx2 client, with redirects followed but capped.
- `DeliveryVerdict`, because a webhook's outcome is a status code and therefore a
  return value. The substrate can only retry what raises, so it retries
  everything to the attempt budget and no receiver can say a failure is terminal;
  modelling the verdict as data is what lets the inner policy stop on `410 Gone`.
- Settings: `TIMEOUT_SECONDS`, `INNER_BACKOFF_BASE_SECONDS`,
  `LEASE_MARGIN_SECONDS` and `MAX_REDIRECTS`.
- Concern subpackages re-export nothing; their `__init__.py` is a docstring. A
  leaf import runs the parent first, so an eager one costs a class of circular
  import for no benefit, and it removes the carve-out the two field validators
  used to need.

- The fan-out: `WebhookDeliveryDue`, `fan_out`, `register_fan_out` and
  `deliver_due`. A domain event becomes one fired event per subscribed endpoint,
  so each delivery carries its own attempt count, backoff, dead-letter and
  replay, and one rotted endpoint cannot drag the others through a retry curve.
- A system check, `django_outbound_webhooks.W001`, for a declared event with no
  fan-out receiver. The fan-out is wired by walking the event registry at
  `ready()`, since the substrate has no wildcard receiver, so listing this app
  before `django_domain_events` leaves events uncovered and nothing raises.
- `DELIVERY_LEASE_SECONDS`, which is both the receiver's lease and the inner
  retry's budget. One setting, because they are the same quantity from two sides.

- The delivery log: `DeliveryAttempt`, one row per HTTP request rather than per
  delivery, carrying the request's body hash and size, the response status and a
  truncated body, the duration and the verdict. The two attempt numbers are named
  for the tier each counts, because they multiply rather than add and a log
  calling either of them "attempt" would make every number in it ambiguous.
- It records failures, which is the half that needed `django-domain-events`
  0.8.0. A receiver's writes are discarded the moment it raises, so before the
  `on_failure` hook this table would have held successes and nothing else.
- The endpoint link is nulled rather than cascaded when a customer deletes an
  endpoint, and the URL is denormalised onto each row: a log whose rows disappear
  with the thing they are evidence about is not a log, and the question it answers
  is where the request went, not where it would go now.
- `LOG_BODY_CHARS`, which bounds how much of a response the log keeps.

### Changed
- The `django-domain-events` floor is now `>=0.8.0`, for the receiver's
  `on_failure` hook.

### Security
- Server-side request forgery is defended at the transport, because that is where
  the defence has to live. `PinningTransport` resolves the hostname, checks
  **every** address it answers with, and then connects to the address it
  checked. Checking a name and handing the name to the connection layer is a race
  rather than a defence: the attacker controls the DNS answer, so a record with a
  one-second lifetime is enough for the resolution that was checked and the
  resolution that is dialled to differ. TLS survives the rewrite because the
  connection layer takes its `server_hostname` from an SNI override, so the
  handshake and the certificate check still use the customer's real hostname.
- `check_address` refuses private, loopback, link-local, reserved, multicast,
  unspecified and carrier-grade NAT addresses. `is_private` alone is the obvious
  single test and it is not enough: measured against Python's own
  classification, carrier-grade NAT and multicast are not private, and the first
  of those is routable inside a provider's network while being unreachable from
  the public internet.
- `ALLOW_PRIVATE_ADDRESSES` relaxes private and loopback only, so a developer can
  deliver to a container or a tunnel. It deliberately does not relax link-local,
  where the cloud metadata endpoint lives, nor multicast, unspecified or
  carrier-grade NAT. "Let me reach localhost" is never a request to reach the
  metadata service.
- `validate_signing_secret` requires real base64. The signing library decodes with
  `validate=False`, so a secret containing any character outside the alphabet has
  that character discarded and the rest decoded to different bytes. It signs
  without complaint and only the customer's verification fails, on their side,
  with no signal on ours.
- Endpoint matching fails closed. An event with no usable tenant value reaches no
  customer endpoint, rather than reaching all of them.

### Fixed
- Timestamps handed to the signing library are converted to UTC first. Its
  `sign` calls `replace(tzinfo=utc)`, which forces the zone rather than
  converting it, so an aware datetime at a non-zero offset would be signed with
  its wall clock read as UTC. The delivery then carries a timestamp wrong by the
  offset and every conforming receiver rejects it as too old or too new, which
  presents as a signature failure carrying a correct signature.

[Unreleased]: https://github.com/Artui/django-outbound-webhooks/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Artui/django-outbound-webhooks/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Artui/django-outbound-webhooks/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Artui/django-outbound-webhooks/compare/v0.0.0...v0.1.0
