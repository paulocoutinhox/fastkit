from dataclasses import dataclass


@dataclass(frozen=True)
class LocaleFormat:
    thousands: str
    decimal: str
    date_format: str
    datetime_format: str
    time_format: str = "%H:%M"


LOCALE_FORMATS = {
    "en": LocaleFormat(
        thousands=",",
        decimal=".",
        date_format="%m/%d/%Y",
        datetime_format="%m/%d/%Y %H:%M",
    ),
    "pt": LocaleFormat(
        thousands=".",
        decimal=",",
        date_format="%d/%m/%Y",
        datetime_format="%d/%m/%Y %H:%M",
    ),
    "es": LocaleFormat(
        thousands=".",
        decimal=",",
        date_format="%d/%m/%Y",
        datetime_format="%d/%m/%Y %H:%M",
    ),
}


def locale_format(locale: str) -> LocaleFormat:
    return LOCALE_FORMATS.get(locale.split("_")[0].lower(), LOCALE_FORMATS["en"])
