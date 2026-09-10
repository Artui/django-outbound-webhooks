"""The migrations load, which is less obvious than it sounds."""

from __future__ import annotations

import importlib

import pytest
from django.db.migrations.loader import MigrationLoader

pytestmark = pytest.mark.django_db


def test_the_apps_migrations_load() -> None:
    # This is a real regression test, not a formality. Django writes a field's
    # validators into the migration as a dotted path, and this package names
    # every module after the single symbol it exports. Re-export such a symbol
    # from the package __init__ and the package attribute *shadows the
    # submodule*: the migration's
    # `django_outbound_webhooks.validate_webhook_url.validate_webhook_url`
    # becomes an attribute lookup on a function and raises AttributeError, at
    # which point no migration in the app can run.
    #
    # It was found by an unrelated test needing a database, which is a poor
    # place to learn it.
    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    ours = [key for key in loader.disk_migrations if key[0] == "django_outbound_webhooks"]
    assert ours, "the app should ship migrations"


def test_the_validator_paths_the_migration_uses_still_resolve() -> None:
    # Naming the exact hazard: each of these has to be importable as
    # module-then-attribute, which is how the migration spells it.
    for module_path, symbol in [
        ("django_outbound_webhooks.validate_webhook_url", "validate_webhook_url"),
        ("django_outbound_webhooks.validate_signing_secret", "validate_signing_secret"),
    ]:
        module = importlib.import_module(module_path)
        assert callable(getattr(module, symbol, None)), (
            f"{module_path}.{symbol} does not resolve. Something re-exported {symbol!r} from "
            f"the package __init__, which shadows the submodule of the same name."
        )
