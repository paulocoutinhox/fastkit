"""What a listing of the site draws under itself, counted in pages because a page is what a person clicks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Paging:
    page: int
    limit: int
    total: int = 0

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.limit))

    def of(self, total: int) -> "Paging":
        """The same request once the listing has been counted, which is what the template needs to draw the last page number."""
        return Paging(page=self.page, limit=self.limit, total=total)
