# django-outbound-webhooks

Guidance for working in this repository.

## What this package is

Outbound webhooks for Django: an endpoint registry a customer writes to, a body
signed to the Standard Webhooks specification, HTTP delivery with a
request-forgery policy, a delivery log, replay and secret rotation.

It is a **durable receiver on `django-domain-events`**, and that is the whole
design. Durability, at-least-once delivery inside the firing transaction, retry
across deliveries, backoff, dead-lettering and replay live in the substrate and
are deliberately not rebuilt here. What lives here is the registry, the
signing, the body format, the transport and the operational surface.

The one-line pitch is that your customers subscribe to domain events, not to
your `post_save` signals.

If a durability feature turns out to be missing, that is a change to
`django-domain-events`. A local workaround here would waste the reason this
package exists. Four such findings are already recorded in the plan.

## Commands

| Command | Does |
| --- | --- |
| `make init` | Sync all dependency groups and install the pre-commit hooks |
| `make test` | pytest with the 100% line+branch coverage gate |
| `make lint` | `ruff check` plus `ty check` |
| `make format-check` | `ruff format --check --diff` (CI runs this; `make lint` does not) |
| `make docs-build` | `mkdocs build --strict` |
| `make release-bump VERSION=X.Y.Z` | Rewrite the version and promote the changelog section |

## Structural rules

Non-negotiable. They keep the package navigable.

1. **One exported class or function per file.** The file is named after the
   exported symbol in `snake_case`.
2. **Private helpers used only in one file** stay in that file with a `_name`
   prefix.
3. **Non-exported helpers shared across files** go in that package's `utils.py`.
4. **Top-level imports only.** Lazy or function-local imports are forbidden
   unless a circular import is proven, or the import targets a declared optional
   dependency gated behind an opt-in. Document the reason inline.
5. **Full type annotations on every function and method signature.** `Any` is
   allowed only at the Django boundary where the type genuinely is `Any`.
6. **`__init__.py` is the only re-export point.** Each `__init__.py` lists the
   public surface in `__all__`. Internal modules import from leaf paths, never
   from the package's `__init__`.
7. **The package root is a table of contents, not a drawer.** It holds
   `__init__.py`, `version.py`, `settings.py`, `apps.py` and nothing else;
   everything the package does lives in a subpackage. A subpackage is named for
   a **concern** (`signing/`, `endpoints/`, `formats/`) and never for a kind of
   thing - `helpers/`, `core/`, `common/` and `misc/` name nothing and become a
   flat root one level down. Three modules on one concern earn a directory.
   `types/` is the one standing subpackage, for value-shape carriers.

   This replaced a rule that read "behavioural code lives at the package
   root", which actively mandated the flat root and had already produced
   same-named module pairs next door in `django-domain-events`. Every rule
   above it governs a file; this is the one that governs a directory, and its
   absence is why a package can obey all six and still put everything in one
   place. There is no `exceptions/`: an exception lives in the subpackage that
   raises it.

## Constraints that look like tidy-ups

Each of these reads as an oversight and is not.

- **Retry numbers must name their tier.** There are two: the substrate retries
  one *delivery*, with its schedule in a database column, surviving restarts;
  this package retries one *HTTP request*, in memory, inside the lease. They
  multiply rather than add, so an auto-disable threshold counted in deliveries
  means something different from one counted in requests. State the unit
  everywhere a number appears, in settings and in the log alike.
- **The inner retry policy is a deadline, not an attempt count.** A receiver
  cannot extend its own lease, so a policy that is unbounded in time can outlast
  the lease with the POST already sent. Another worker then takes the row and
  this worker's write is rolled back, so the customer has the delivery and the
  log does not. Use `stop_before_delay`, and derive the deadline from
  `lease_seconds` **minus the per-request timeout**: `stop_before_delay` keeps
  the next *sleep* inside the limit and knows nothing about how long the attempt
  after it will take.
- **Never reach for `tenacity` for the outer tier**, however much
  `wait_exponential_jitter` resembles the substrate's `backoff()`. Its state is
  an object in memory, so a deploy mid-backoff loses the schedule, where
  `available_at` is a column.
- **A published format version is frozen.** An endpoint pins the format version
  it was integrated against, so changing what an old version renders changes
  what an already-integrated consumer receives. A change is a new version. The
  golden fixtures are what enforce this; see Tests.
- **Formats are operator-registered and customer-selected, never
  customer-written.** A customer-supplied template is an injection surface, and
  it sits directly against the tenant boundary below.
- **Endpoint matching is a data-isolation boundary, not routing.** Which
  endpoints receive an event decides whether one customer's payload reaches
  another customer's URL, correctly signed. Match on the event's scope
  explicitly and **fail closed**: an event carrying no tenant scope goes to no
  customer endpoint, never to all of them.

## Two things this package's own conventions collide with

Both were found by hitting them, and both will recur.

- **A callable Django serialises into a migration must not live at a path the
  package `__init__` shadows.** One-symbol-per-file means a module is named after
  the symbol it exports, and re-exporting that symbol from `__init__` makes the
  package attribute win: `import django_outbound_webhooks.validate_webhook_url`
  then binds the **function**, so the migration's dotted path becomes an
  attribute lookup on a function and **no migration in the app can run**. The two
  field validators are therefore not re-exported. The same applies to a
  `default=` callable, an `upload_to=` and a `through=`. `tests/test_migrations.py`
  names the hazard; it first surfaced through an unrelated database test. It
  applies at every depth: a subpackage `__init__` shadows its own submodules
  exactly as the package root does, which is why neither `signing/__init__.py`
  nor `endpoints/__init__.py` re-exports its validator either.

  **Moving such a module is a cost, not a law, and the owner prices it.** The
  cost is proportional to installs with history, which for this package is
  **zero** - nothing has been published and `0001_initial` has never reached
  `main`. That is why both validators moved into their concern groups on
  2026-09-10 and the migration was regenerated with them. Once there is a
  release, the answer changes.
- **`ty` cannot see a foreign key's implicit `<fk>_id`**, because Django creates
  it at runtime and ty has no Django support. Do not reach for django-stubs, a
  newer ty, a config setting or a different declaration style; all four were
  measured and none of them helps. Tracked upstream as astral-sh/ty#1018.
  **Traverse the relation instead of reading the id**: `self.endpoint.name` needs
  no annotation and is the better string anyway, since a name is what a customer
  calls their endpoint and a primary key means nothing to them. It costs one
  query on an instance that did not fetch the relation, so a listing that renders
  it needs `select_related`. There are no `<fk>_id` reads left in this package.
  If a traversal is ever the wrong answer, declare a bare annotation beside the
  field rather than suppressing the rule: the annotation supplies a real type,
  where a suppression leaves the attribute unknown.

## Adding a feature

Branch first, always. Three touchpoints per change: the source file, the
`__init__.py` re-export, and the mirrored test file.

## Tests

`tests/` mirrors the source tree, one file per source file with the same name.
`pytest-asyncio` runs in auto mode. The coverage gate is **100% line and
branch**.

Never `# pragma: no cover`. If a branch cannot be reached, that is a signal to
restructure the code, not to exempt it.

Rules specific to this package:

- **Assert against the transport, not against a mocking library.** The suite
  stubs `httpx2.MockTransport`, which is the transport the code under test
  actually calls. `respx` is the obvious reach and it declares `httpx`, so
  adding it would install a second HTTP client and every wire assertion would be
  made against the one this package does not use.
- **Every published format version needs a golden fixture, byte for byte,
  generated by this package's own renderer and checked in with its generator.**
  Regenerate and diff to verify. Never hand-type the expected bytes. This is
  what makes "immutable once published" a gate rather than a note, and it is the
  only mechanism here that goes red when someone edits an old formatter.
- **A retry test must distinguish the tiers.** One that counts HTTP requests
  without pinning which tier produced them passes under either reading.
- **Test the lease boundary by exceeding it**, not by asserting the policy
  object. The failure being guarded against is a delivery that was sent and not
  recorded, and only a test that runs past the lease can show it.
- **A signature test reads the bytes that were sent.** A round trip through this
  package's own signer proves agreement, not conformance. Verify against a
  fixture of the specification's own example.

## Type checking

`ty`, scoped to `django_outbound_webhooks` via `[tool.ty.environment]`. The
package ships `py.typed`, so consumers get the annotations.

Never a mypy-style `# type: ignore` in the package - a pre-commit hook rejects
it, because nothing here reads that pragma and leaving one implies a checker
that is not running.

## Linting and formatting

`ruff` is the source of truth for both. Use `...` rather than `pass` for empty
bodies.

`make lint` does **not** run `ruff format --check`, and CI does. Run
`uv run ruff format --check` before pushing.

## Imports inside the package

Absolute and fully qualified, never relative - `ban-relative-imports = "all"` is
configured and enforced. isort order is stdlib, third party, first party.

`from __future__ import annotations` goes at the top of every annotated file.
`required-imports` in the isort config is what enforces it rather than leaving
it to memory, and the two exemptions are re-export `__init__.py` files and
Django's generated migrations.

## Compatibility floor

| | Minimum | Tested against |
| --- | --- | --- |
| Python | 3.10 | 3.10 through 3.14 |
| Django | 4.2 | 4.2, 5.0, 5.1, 5.2, 6.0, 6.1 |
| django-domain-events | 0.7.0 | the floor job resolves it |

The `django-domain-events` floor is **0.7.0 for a reason**: it is the release
whose delivery rows carry the lease the inner retry policy is bounded by. Below
it there is no lease to bound against, and the policy silently becomes the
unbounded one this package exists to avoid. Do not lower it.

The suite runs on SQLite throughout. Everything this package owns is
backend-neutral; the machinery that genuinely needs a real server lives in the
substrate and is tested there against Postgres. If a Postgres-only path ever
lands here, the coverage gate has to move with it.

## CI and pre-commit

Seven jobs in `tests.yml`: `lint`, `docs`, `floor` (resolves every declared
dependency at the bottom of its window and runs the suite there), `test` (the
Python x Django matrix), `coverage-badge`, `secrets`, and the `tests-passed`
gate that branch protection points at.

Releases are **main-triggered**: `make release-bump`, edit the changelog, open a
PR, and merging to `main` runs the release. There is no tag to push - the
workflow creates the tag after PyPI accepts the upload, which is also why
`make release-publish-finalize` exists for the case where it does not.

Pre-commit runs gitleaks, the standard hygiene hooks, ruff, ty, four convention
guards (no local filesystem paths, no internal plan-step labels, no mypy-style
type-ignore, no emoji or marker glyphs in any committed file) and
`check-changelog`, which refuses a changelog a merge or rebase has silently
rearranged.

## Releasing

```
make release-bump VERSION=X.Y.Z   # rewrites version.py, promotes the changelog
# edit CHANGELOG.md to fill in the new section, review the diff
# open a PR, get it reviewed, merge to main
```

The release job on `main` short-circuits to a no-op when a `vX.Y.Z` tag for the
version in source already exists on origin, so an ordinary merge costs nothing.

That guard is why the scaffold sits at `0.0.0` with a matching `v0.0.0` tag. A
new repository has no tags at all, so without one the very first push to `main`
reads the scaffold version as unreleased and runs a real release attempt. The
first real release is `make release-bump VERSION=0.1.0`.

One-time setup that cannot be done from a checkout: a PyPI Trusted Publisher
pointing at this repo with workflow `release.yml` and environment `pypi`.
