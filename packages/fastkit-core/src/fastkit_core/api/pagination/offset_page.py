from dataclasses import dataclass


@dataclass(frozen=True)
class OffsetPage:
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0

        return (self.total_items + self.page_size - 1) // self.page_size

    def to_meta(self) -> dict:
        return {
            "strategy": "offset",
            "page": self.page,
            "page_size": self.page_size,
            "total_items": self.total_items,
            "total_pages": self.total_pages,
            "has_previous": self.page > 1,
            "has_next": self.page < self.total_pages,
        }
