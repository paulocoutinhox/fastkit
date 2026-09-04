"""Which tenant a row belongs to, and which ones a reader reaches."""

from sqlalchemy import or_


def reaches_tenant(column, tenant_id: int | None):
    """A row without a tenant is shared with every one of them, and `IN (id, NULL)` would never match it."""
    return or_(column == tenant_id, column.is_(None))


def belongs_to_tenant(column, tenant_id: int | None):
    """The one scope a row sits in, where no tenant means the global scope and never every scope — an identity is unique inside this, not inside what a tenant reaches."""
    return column.is_(None) if tenant_id is None else column == tenant_id
