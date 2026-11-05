import re

from helpers.money import places

# The characters a sheet name refuses, and the length it stops at.
SHEET_REFUSES = re.compile(r"[\[\]:*?/\\]")

SHEET_NAME_MAX = 31

DATE_FORMAT = "yyyy-mm-dd"

DATETIME_FORMAT = "yyyy-mm-dd hh:mm"


class ExcelBook:
    """A spreadsheet being written, with the cell formats every sheet of a report shares made once, which a format of a report's own writes its sheets with."""

    def __init__(self, workbook):
        self.workbook = workbook
        self.heading = workbook.add_format({"bold": True, "bottom": 1})
        self.title = workbook.add_format({"bold": True, "font_size": 12})
        self.dated = workbook.add_format({"num_format": DATE_FORMAT})
        self.timed = workbook.add_format({"num_format": DATETIME_FORMAT})
        self.amounts: dict[str, object] = {}

    def sheet(self, name: str):
        """A sheet named the way a spreadsheet accepts, and never a name another sheet of the file already took."""
        named = SHEET_REFUSES.sub(" ", name)[:SHEET_NAME_MAX]
        taken = {sheet.name.lower() for sheet in self.workbook.worksheets()}
        suffix = 2

        while named.lower() in taken:
            ending = f" ({suffix})"
            named = SHEET_REFUSES.sub(" ", name)[: SHEET_NAME_MAX - len(ending)] + ending
            suffix += 1

        return self.workbook.add_worksheet(named)

    def amount(self, currency: str):
        """The format of an amount, which keeps its cell a number a sum still adds and names the currency so a sheet of two currencies never reads as one."""
        if currency not in self.amounts:
            self.amounts[currency] = self.workbook.add_format({"num_format": self.amount_format(currency)})

        return self.amounts[currency]

    def amount_format(self, currency: str) -> str:
        decimals = places(currency)
        fraction = "." + "0" * decimals if decimals else ""

        return f'"{currency.upper()}" #,##0{fraction}'
