from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    """Everything a delivery needs that must not change between its attempts."""

    endpoint_id: int
    format_name: str
    format_version: int
    message_id: str

    def encode(self) -> str:
        return json.dumps(
            {
                "endpoint": self.endpoint_id,
                "format": self.format_name,
                "version": self.format_version,
                "message": self.message_id,
            },
            separators=(",", ":"),
        )

    @classmethod
    def decode(cls, target: str) -> DeliveryTarget:
        fields = json.loads(target)
        return cls(
            endpoint_id=fields["endpoint"],
            format_name=fields["format"],
            format_version=fields["version"],
            message_id=fields["message"],
        )
