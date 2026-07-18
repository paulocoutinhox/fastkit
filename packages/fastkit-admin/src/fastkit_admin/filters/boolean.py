from fastkit_admin.filters.base import Filter


class BooleanFilter(Filter):
    filter_type = "boolean"

    def apply(self, query, model, value):
        if value in (None, ""):
            return query

        truthy = value in (True, "true", "1", 1)

        return query.where(self.column(model).is_(truthy))
