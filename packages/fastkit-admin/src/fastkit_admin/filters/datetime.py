from fastkit_admin.filters.equality import EqualityFilter


class DateTimeFilter(EqualityFilter):
    filter_type = "datetime"
