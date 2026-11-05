from schemas.base_schema import BaseSchema


class ChartPaletteSchema(BaseSchema):
    """The colours a chart paints its series with, in the order a series takes them, for each side of the panel's palette."""

    light: list[str]
    dark: list[str]
