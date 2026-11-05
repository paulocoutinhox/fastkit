from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# A colour as every renderer reads one: the screen, the printed page and the spreadsheet.
Colour = Annotated[str, Field(pattern=r"^#[0-9a-f]{6}$")]


class ChartSettings(BaseModel):
    """The colours a chart paints its series with, in the fixed order a series takes them, stepped once for a light surface and once for a dark one."""

    # The order is what keeps two neighbouring series apart for a reader with a colour vision deficiency, so a slot is replaced and never reordered without validating the set again.
    light: tuple[Colour, ...] = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
    dark: tuple[Colour, ...] = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")

    @model_validator(mode="after")
    def each_slot_in_both_themes(self):
        if len(self.light) != len(self.dark) or not self.light:
            raise ValueError("a chart palette names the same slots for the light surface and the dark one")

        return self

    @property
    def slots(self) -> int:
        return len(self.light)
