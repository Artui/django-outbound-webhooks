from __future__ import annotations

import pytest
from django.test import override_settings

from django_outbound_webhooks.settings import DEFAULTS, setting


def test_an_unconfigured_key_takes_its_default() -> None:
    assert setting("DEFAULT_FORMAT") == DEFAULTS["DEFAULT_FORMAT"]


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"DEFAULT_FORMAT": "cloudevents"})
def test_a_configured_key_wins() -> None:
    assert setting("DEFAULT_FORMAT") == "cloudevents"


@override_settings(DJANGO_OUTBOUND_WEBHOOKS={"DEFAULT_FORMAT": "cloudevents"})
def test_a_partial_configuration_still_defaults_the_rest() -> None:
    # A project that sets one key must not lose the others.
    assert setting("DEFAULT_FORMAT") == "cloudevents"
    assert set(DEFAULTS) >= {"DEFAULT_FORMAT"}


def test_an_unknown_key_raises_rather_than_returning_none() -> None:
    with pytest.raises(KeyError):
        setting("NO_SUCH_SETTING")
