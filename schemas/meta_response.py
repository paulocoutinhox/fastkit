from schemas.authentication_methods_response import AuthenticationMethodsResponse
from schemas.base_schema import BaseSchema
from schemas.chart_palette_schema import ChartPaletteSchema
from schemas.credential_schema import CredentialSchema


class MetaResponse(BaseSchema):
    name: str
    environment: str
    version: str
    storage_base_url: str
    enums: dict[str, list[str]]
    provider_credentials: dict[str, list[CredentialSchema]]
    timezones: list[str]
    authentication: AuthenticationMethodsResponse
    chart_palette: ChartPaletteSchema
