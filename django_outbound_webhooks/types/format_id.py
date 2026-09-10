"""The identity of one published body format."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatId:
    """A format name and the version of it an endpoint is pinned to.

    Two fields rather than one string because they are compared differently:
    the name selects a renderer family and the version selects one frozen
    member of it. A single ``"envelope@1"`` string would make every lookup a
    parse, and every parse a place to accept a version that was never
    published.

    Ordering matters for exactly one thing -- reporting which versions are
    still pinned, so an old one can be retired once nothing names it -- so the
    ordering is on the version and the name is the tiebreak.
    """

    name: str
    version: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("A format name cannot be empty.")
        if self.version < 1:
            raise ValueError(f"Format versions start at 1; got {self.version} for {self.name!r}.")

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"
