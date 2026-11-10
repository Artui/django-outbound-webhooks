from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedBody:
    """What gets signed and sent."""

    body: bytes
    content_type: str

    def __post_init__(self) -> None:
        if not self.content_type:
            raise ValueError("A rendered body has to say what content type it is.")
