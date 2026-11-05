from schemas.common import as_optional
from schemas.country_create import CountryCreate

CountryUpdate = as_optional("CountryUpdate", CountryCreate)
