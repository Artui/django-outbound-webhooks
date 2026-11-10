from __future__ import annotations

import pytest

from django_outbound_webhooks.types.format_id import FormatId


def test_it_reads_as_name_at_version() -> None:
    assert str(FormatId(name="envelope", version=1)) == "envelope@1"


def test_it_is_hashable_and_compares_by_value() -> None:
    assert FormatId(name="envelope", version=1) == FormatId(name="envelope", version=1)
    assert len({FormatId(name="envelope", version=1), FormatId(name="envelope", version=1)}) == 1


def test_an_empty_name_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        FormatId(name="", version=1)


@pytest.mark.parametrize("version", [0, -1])
def test_versions_start_at_one(version: int) -> None:
    with pytest.raises(ValueError, match="start at 1"):
        FormatId(name="envelope", version=version)
