"""What a postal code stands for, asked of the service of the country that has one."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from enums.country import PostalCodeProvider
from helpers import remote
from helpers.text import only_digits

TIMEOUT = 5.0


@dataclass(frozen=True)
class PostalAddress:
    """What a postal code stands for, in the shape the address form of this side is written in."""

    line1: str = ""
    district: str = ""
    city: str = ""
    state: str = ""


class PostalCodeLookup(ABC):
    """One country is answered by one service, and a country with none draws a plain field instead of asking anybody."""

    provider: PostalCodeProvider

    @abstractmethod
    async def find(self, postal_code: str) -> PostalAddress | None: ...


class ViaCep(PostalCodeLookup):
    """Read against the current documentation of viacep.com.br, which answers a lookup as `/ws/<eight digits>/json/`."""

    provider = PostalCodeProvider.VIACEP

    async def find(self, postal_code: str) -> PostalAddress | None:
        digits = only_digits(postal_code)

        # A code of any other length is one the service answers 400 to, so it is refused here instead of asked about.
        if len(digits) != 8:
            return None

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            answered = await client.get(f"https://viacep.com.br/ws/{digits}/json/")

        if answered.status_code != httpx.codes.OK:
            return None

        body = remote.body_of(answered)

        # A code nobody knows is answered with `erro` and a status of 200, so the body is what says it was not found.
        if body.get("erro"):
            return None

        place = PostalAddress(line1=body.get("logradouro") or "", district=body.get("bairro") or "", city=body.get("localidade") or "", state=body.get("uf") or "")

        # A postal code stands for a place, so a body naming none is one that found nothing however cleanly it answered.
        return place if place.city and place.state else None


PROVIDERS: dict[PostalCodeProvider, PostalCodeLookup] = {PostalCodeProvider.VIACEP: ViaCep()}


async def find(provider: PostalCodeProvider, postal_code: str) -> PostalAddress | None:
    return await PROVIDERS[provider].find(postal_code)
