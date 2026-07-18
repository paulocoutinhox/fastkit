from fastkit_admin.filters.equality import EqualityFilter


class ExactFilter(EqualityFilter):
    filter_type = "exact"
