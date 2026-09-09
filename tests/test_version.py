"""The version is a single source of truth, and the package is a Django app."""

from __future__ import annotations

import re

from django.apps import apps

import django_outbound_webhooks
from django_outbound_webhooks.version import __version__

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_a_release_number() -> None:
    assert SEMVER.match(__version__), __version__


def test_the_package_root_re_exports_the_same_object() -> None:
    # version.py is the single source of truth and __init__.py re-exports it.
    # Two copies of the string would pass an equality check while drifting on
    # the next bump, so this asserts identity rather than equality.
    assert django_outbound_webhooks.__version__ is __version__


def test_the_package_loads_as_a_django_app() -> None:
    # It goes into INSTALLED_APPS, so "does it import" is not the question --
    # whether Django's registry can load it is.
    assert apps.is_installed("django_outbound_webhooks")
