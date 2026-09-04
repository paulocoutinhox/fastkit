"""A palette is only a palette where the text on it can be read, and a ratio is measured rather than judged by eye."""

import math
import pathlib
import re

STYLESHEETS = ("webapps/admin/src/style.css",)

# What sits on what, across the screens of both surfaces.
PAIRS = [
    ("ink", "raised"),
    ("ink", "surface"),
    ("ink", "sunken"),
    ("ink-soft", "raised"),
    ("ink-soft", "surface"),
    ("ink-muted", "raised"),
    ("ink-muted", "surface"),
    ("ink-muted", "sunken"),
    ("danger", "raised"),
    ("danger-ink", "danger-soft"),
    ("good-ink", "good-soft"),
    ("notice", "notice-soft"),
    ("brand-ink", "raised"),
    ("brand-ink", "surface"),
]

# What is de-emphasised on purpose, which the guidelines hold to the ratio of large text rather than of prose.
FAINT = [("ink-faint", "raised"), ("ink-faint", "surface")]

READABLE = 4.5

SEEN = 3.0


def declared(name: str) -> str:
    """A stylesheet and the brand the build writes beside it, which together are the palette this surface draws with."""
    sheet = pathlib.Path(name)

    return sheet.read_text() + (sheet.parent / "brand.css").read_text()


def sides(css: str) -> tuple[dict, dict]:
    """Both palettes, read out of the one declaration that carries them, following the brand the build writes beside them."""
    light, dark = {}, {}
    brand = {}

    # The brand does not turn with the palette, so a step of it is the same colour on both sides.
    for name, colour in re.findall(r"--(brand-[\w-]+):\s*(oklch\([^)]*\))", css):
        brand[name] = (colour, colour)

    for name, first, second in re.findall(r"--color-([\w-]+):\s*light-dark\(([^,]+),\s*([^)]+\))\)", css):
        light[name] = first.strip()
        dark[name] = second.strip()

    for name, pointed in re.findall(r"--color-([\w-]+):\s*var\(--([\w-]+)\)", css):
        if pointed in brand:
            light[name], dark[name] = brand[pointed]

    # A side of a pair names a step of the brand where it turns with the palette, so the name is followed there too.
    for side in (light, dark):
        for name, value in list(side.items()):
            pointed = re.fullmatch(r"var\(--(brand-[\w-]+)\)", value)

            if pointed:
                side[name] = brand[pointed.group(1)][0]

    return light, dark


def rgb_of(colour: str) -> tuple[float, float, float]:
    # A stylesheet writes the lightness as a percentage and drops the nought of a fraction, and a declaration writes neither.
    found = re.match(r"oklch\(\s*(\.?[\d.]+)(%?)\s+(\.?[\d.]+)\s+(\.?[\d.]+)", colour)

    assert found is not None, f"{colour} is not a colour this reads"

    lightness = float(found.group(1)) / (100 if found.group(2) else 1)
    chroma, hue = float(found.group(3)), float(found.group(4))
    angle = math.radians(hue)
    a, b = chroma * math.cos(angle), chroma * math.sin(angle)
    one, two, three = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3, (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3, (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    red = 4.0767416621 * one - 3.3077115913 * two + 0.2309699292 * three
    green = -1.2684380046 * one + 2.6097574011 * two - 0.3413193965 * three
    blue = -0.0041960863 * one - 0.7034186147 * two + 1.7076147010 * three

    return tuple(max(0.0, min(1.0, value)) for value in (red, green, blue))


def brightness(colour: str) -> float:
    """What the eye receives, weighted, and read straight off the linear channels because that is what oklch answers in."""
    red, green, blue = rgb_of(colour)

    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def between(one: str, two: str) -> float:
    first, second = brightness(one), brightness(two)

    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def test_every_palette_carries_both_sides_of_itself_in_one_declaration():
    """Written apart, the two are two things to remember, and the one nobody edits is the one that rots."""
    for name in STYLESHEETS:
        css = declared(name)
        light, dark = sides(css)

        assert len(light) >= 30, f"{name} declares only {len(light)} colours, so this is proving nothing"
        assert set(light) == set(dark)
        assert ".dark {" not in css and "prefers-color-scheme" not in css, f"{name} says what dark is in a second place"


def test_text_can_be_read_on_the_surface_it_sits_on():
    for name in STYLESHEETS:
        light, dark = sides(declared(name))

        for palette, which in ((light, "light"), (dark, "dark")):
            for ink, ground in PAIRS:
                found = between(palette[ink], palette[ground])

                assert found >= READABLE, f"{name}: {ink} on {ground} in {which} is {found:.2f}:1, and prose needs {READABLE}:1"

            for ink, ground in FAINT:
                found = between(palette[ink], palette[ground])

                assert found >= SEEN, f"{name}: {ink} on {ground} in {which} is {found:.2f}:1, and even a faint thing needs {SEEN}:1"


def test_a_solid_fill_carries_white_in_either_palette():
    """A fill flips nothing, because the text on it is white on both sides and a lighter red would lose it."""
    for name in STYLESHEETS:
        light, dark = sides(declared(name))

        for fill in ("danger-fill", "good-fill", "brand-600"):
            for palette, which in ((light, "light"), (dark, "dark")):
                found = between(palette[fill], "oklch(1 0 0)")

                assert found >= SEEN, f"{name}: white on {fill} in {which} is {found:.2f}:1"


# The two palettes the site draws with, which the plugin writes rather than this project.
THEMES = {"light": r':root:has\(input\.theme-controller\[value=light\]:checked\),\[data-theme="?light"?\]|:root\b', "black": r'\[data-theme="?black"?\]'}

# What the templates put on what, in the words the plugin uses.
DRAWN = [("base-content", "base-100"), ("base-content", "base-200"), ("primary", "base-100"), ("error", "base-100"), ("success", "base-100"), ("warning", "base-100"), ("primary-content", "primary"), ("error-content", "error")]


def stated(css: str) -> dict:
    """Every value each theme states for each of its colours, read from every block that names the theme rather than from one of them."""
    # The brand is written by the build and pointed at, so a theme states its primary as a name and not as a colour.
    brand = dict(re.findall(r"(--brand-[\w-]+):\s*(oklch\([^)]*\))", css))
    found = {}

    for block in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        selector, body = block.group(1), block.group(2)

        # A block is read only where its selector names the theme, because a bare `:root` inside a dark media query is not the light one.
        themes = {first or second for first, second in re.findall(r"data-theme=\"?(\w+)\"?|theme-controller\[value=(\w+)\]", selector)}

        for theme in themes:
            for colour, value in re.findall(r"--color-([\w-]+):\s*(oklch\([^)]*\)|var\(--brand-[\w-]+\))", body):
                pointed = re.fullmatch(r"var\((--brand-[\w-]+)\)", value)
                found.setdefault(theme, {}).setdefault(colour, set()).add(brand[pointed.group(1)] if pointed else value)

    return found


def painted(css: str) -> dict:
    """The one colour each theme paints with, which is only one where nothing else declares the same token for that theme."""
    return {theme: {colour: next(iter(values)) for colour, values in colours.items()} for theme, colours in stated(css).items()}


def test_the_site_draws_with_two_palettes_and_both_can_be_read():
    """The plugin ships a black theme that is monochrome, so what this project asks of it is measured rather than trusted."""
    built = pathlib.Path("webapps/site/dist/styles.css")

    assert built.is_file(), "the site has not been built, and this measures what a browser is given"

    themes = painted(built.read_text())

    assert {"light", "black"} <= set(themes), f"the stylesheet carries {sorted(themes)}"

    for name in ("light", "black"):
        palette = themes[name]

        for ink, ground in DRAWN:
            if ink not in palette or ground not in palette:
                continue

            found = between(palette[ink], palette[ground])

            assert found >= SEEN, f"{name}: {ink} on {ground} is {found:.2f}:1, and nothing drawn on a surface may sit under {SEEN}:1"

    # A page and the card on it are two surfaces, and one that matches the other is a card with no edge.
    for name in ("light", "black"):
        palette = themes[name]

        assert palette["base-100"] != palette["base-200"], f"{name}: a card is the same colour as the page it sits on"


def test_a_theme_of_the_site_states_each_of_its_colours_once():
    """Naming a theme twice writes the stock palette into a selector of higher specificity, and the tuned value below it loses in the browser."""
    built = pathlib.Path("webapps/site/dist/styles.css")

    assert built.is_file(), "the site has not been built, and this measures what a browser is given"

    stated_twice = []
    read = 0

    for theme, colours in stated(built.read_text()).items():
        read += len(colours)
        stated_twice += [f"{theme}: {colour} is stated as {sorted(values)}" for colour, values in colours.items() if len(values) > 1]

    assert read >= 30
    assert stated_twice == []
