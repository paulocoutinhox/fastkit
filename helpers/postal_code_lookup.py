"""One country is answered by one service, and a country with none draws a plain field instead of asking anybody."""

from abc import ABC, abstractmethod

from helpers.postal_address import PostalAddress


class PostalCodeLookup(ABC):
    @abstractmethod
    async def find(self, postal_code: str) -> PostalAddress | None: ...
