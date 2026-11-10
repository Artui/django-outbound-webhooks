from __future__ import annotations

import importlib

import pytest
from django.db.migrations.loader import MigrationLoader

pytestmark = pytest.mark.django_db


def test_the_apps_migrations_load() -> None:
    # This is a real regression test, not a formality.
    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    ours = [key for key in loader.disk_migrations if key[0] == "django_outbound_webhooks"]
    assert ours, "the app should ship migrations"


def test_the_validator_paths_the_migration_uses_still_resolve() -> None:
    for module_path, symbol in [
        ("django_outbound_webhooks.endpoints.validate_webhook_url", "validate_webhook_url"),
        ("django_outbound_webhooks.signing.validate_signing_secret", "validate_signing_secret"),
    ]:
        module = importlib.import_module(module_path)
        assert callable(getattr(module, symbol, None)), (
            f"{module_path}.{symbol} does not resolve. Something re-exported {symbol!r} from "
            f"a package __init__, which shadows the submodule of the same name."
        )


def test_no_migration_is_missing() -> None:
    from django.core.management import call_command

    call_command("makemigrations", "django_outbound_webhooks", "--check", "--dry-run", verbosity=0)
