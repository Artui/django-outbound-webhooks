from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatId:
    """A format name and the version of it an endpoint is pinned to."""

    name: str
    version: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("A format name cannot be empty.")
        if self.version < 1:
            raise ValueError(f"Format versions start at 1; got {self.version} for {self.name!r}.")

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"
