from fastkit_admin.filters.base import Filter


class TextFilter(Filter):
    filter_type = "text"

    def apply(self, query, model, value):
        if not value:
            return query

        return query.where(self.column(model).ilike(f"%{value}%"))
