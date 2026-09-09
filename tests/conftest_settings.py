"""Settings for the test suite.

SQLite in memory throughout: this package owns an endpoint registry, a body
format and an HTTP client, and every one of those is backend-neutral. The
durability machinery that genuinely needs a real server lives in
``django_domain_events`` and is tested there against Postgres.
"""

from __future__ import annotations

SECRET_KEY = "not-a-secret-this-is-the-test-suite"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    # The substrate ships the event and delivery tables this package's
    # receivers are registered against, so its app has to be installed for
    # either package's models to load.
    "django_domain_events",
    "django_outbound_webhooks",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True
