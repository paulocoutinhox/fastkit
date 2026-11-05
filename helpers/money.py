"""The smallest unit of each currency, which is what a gateway charges in, and how a person reads an amount of it."""

from decimal import ROUND_HALF_UP, Decimal

# A gateway states an amount in the smallest unit of its currency, and how small that is is a property of the currency.
ZERO_DECIMAL = frozenset({"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"})
THREE_DECIMAL = frozenset({"bhd", "jod", "kwd", "omr", "tnd"})


def factor(currency: str) -> int:
    lowered = currency.lower()

    if lowered in ZERO_DECIMAL:
        return 1

    if lowered in THREE_DECIMAL:
        return 1000

    return 100


def minor_units(amount: Decimal, currency: str) -> int:
    """What a gateway is told to charge, which is a whole number of the smallest unit and never a decimal."""
    # A price carries two decimals whatever the currency does, and truncating one that keeps fewer charges less than the sticker said.
    return int((amount * factor(currency)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_minor_units(amount: int, currency: str) -> Decimal:
    return Decimal(amount) / factor(currency)


# How each language groups a number and where it puts the code of a currency, which is not the same question as how small the currency divides.
# Both are indexed and never reached with a default, because a language added without a format would silently read as English.
GROUPING = {"en": (",", "."), "pt": (".", ","), "es": (".", ",")}

# A code is a word and keeps its space wherever the language puts it.
PLACEMENT = {"en": "{code} {value}", "pt": "{code} {value}", "es": "{value} {code}"}


def places(currency: str) -> int:
    """How many decimals this currency divides into, which is what its smallest unit says."""
    return len(str(factor(currency))) - 1


def number(value: Decimal | int | float, locale: str, decimals: int = 0) -> str:
    """A number the way somebody reading this language writes one."""
    thousands, point = GROUPING[locale]
    quantized = Decimal(value).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    whole, _, fraction = f"{abs(quantized):f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", thousands)
    sign = "-" if quantized < 0 else ""

    return f"{sign}{grouped}{point}{fraction}" if fraction else f"{sign}{grouped}"


def money(amount: Decimal | int | float, currency: str, locale: str) -> str:
    """An amount as it is read, named by the code of its currency where the language of the reader puts one."""
    return PLACEMENT[locale].format(code=currency.upper(), value=number(amount, locale, places(currency)))
