"""The bytes a format produced, and how to label them on the wire."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedBody:
    """What gets signed and sent.

    ``body`` is bytes rather than str on purpose. The signature is computed over
    the body, and the delivery log records its hash, so any encoding step
    between rendering and signing is a place where the bytes that were hashed
    stop being the bytes that were sent. Encoding happens once, here, and
    everything downstream handles bytes.
    """

    body: bytes
    content_type: str

    def __post_init__(self) -> None:
        if not self.content_type:
            raise ValueError("A rendered body has to say what content type it is.")
