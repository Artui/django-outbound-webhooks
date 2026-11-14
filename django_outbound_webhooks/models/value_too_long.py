from __future__ import annotations


class ValueTooLong(ValueError):
    """A value longer than its column holds, refused before the write reaches the database."""

    def __init__(self, *, model: str, field: str, length: int, limit: int) -> None:
        self.model = model
        self.field = field
        self.length = length
        self.limit = limit
        super().__init__(
            f"{model}.{field} is {length} characters long and holds at most {limit}. "
            f"The value is refused before the write, on every backend."
        )
