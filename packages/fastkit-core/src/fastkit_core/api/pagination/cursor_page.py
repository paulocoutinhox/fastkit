from dataclasses import dataclass


@dataclass(frozen=True)
class CursorPage:
    next_cursor: str | None
    previous_cursor: str | None

    def to_meta(self) -> dict:
        return {
            "strategy": "cursor",
            "next_cursor": self.next_cursor,
            "previous_cursor": self.previous_cursor,
            "has_next": self.next_cursor is not None,
            "has_previous": self.previous_cursor is not None,
        }
