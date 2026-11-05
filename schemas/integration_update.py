from schemas.common import as_optional
from schemas.integration_create import IntegrationCreate

IntegrationUpdate = as_optional("IntegrationUpdate", IntegrationCreate)
