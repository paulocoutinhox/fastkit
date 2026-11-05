"""What a postal code stands for, asked of the service of the country that has one."""

from enums.postal_code_provider import PostalCodeProvider
from helpers.postal_address import PostalAddress
from helpers.postal_code_lookup import PostalCodeLookup
from helpers.via_cep import ViaCep

PROVIDERS: dict[PostalCodeProvider, PostalCodeLookup] = {PostalCodeProvider.VIACEP: ViaCep()}


async def find(provider: PostalCodeProvider, postal_code: str) -> PostalAddress | None:
    return await PROVIDERS[provider].find(postal_code)
