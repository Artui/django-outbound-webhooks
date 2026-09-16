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
    "django.contrib.messages",
    "django.contrib.sessions",
    # Installed rather than stubbed. The admin integration is a package named
    # `admin`, and whether Django's autodiscovery imports it -- and therefore
    # whether either ModelAdmin is registered at all -- is exactly the thing
    # worth testing. A ModelAdmin instantiated by hand in a test passes with the
    # package never loaded.
    "django.contrib.admin",
    # Deliberately *before* django_domain_events, which is the order that used
    # to break delivery silently. This package's ready() declares its receiver
    # before the substrate's ready() has autodiscovered a single events.py, so
    # every event the suite fires was declared after the receiver existed. The
    # receiver is a wildcard matched at fire time, and this order is what makes
    # the whole suite say so rather than one test.
    "django_outbound_webhooks",
    # The substrate ships the event and delivery tables this package's
    # receivers are registered against, so its app has to be installed for
    # either package's models to load.
    "django_domain_events",
    "tests.testapp",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

ROOT_URLCONF = "tests.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True

DJANGO_OUTBOUND_WEBHOOKS = {
    # Publishes the CloudEvents format for the whole suite, because it is
    # published only for a deployment that says which system produced its
    # events. Registration happens once, in AppConfig.ready(), so a test cannot
    # turn this on afterwards -- which is why register_built_in_formats takes
    # the registry as an argument: the unpublished half is asserted against a
    # fresh one instead of by re-running ready().
    "CLOUDEVENTS_SOURCE": "https://shop.example/events",
}
