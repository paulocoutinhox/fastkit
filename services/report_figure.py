import math
from io import StringIO

import matplotlib
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, FuncFormatter, MaxNLocator

from enums.report_chart_kind import ReportChartKind
from helpers.money import number
from helpers.settings import settings
from services.report_plot import SLICED, ReportPlot

# The ink of a printed chart, which recedes behind the marks it frames: the title, the labels of an axis, the grid and the line a bar stands on.
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#ffffff"

# How many labels an axis of points writes at most before skipping some, past which they would run into each other.
TICKS_MAX = 5

# A label of a point past this length is cut on paper, where it cannot be hovered to be read whole.
LABEL_MAX = 28

# What the figure is drawn with: its text stays text so the page writes it in the font of the document, and a dollar sign in a product name is a dollar sign and never the start of a formula.
STYLE = {"svg.fonttype": "none", "svg.hashsalt": "report", "font.family": "DejaVu Sans", "font.size": 8, "text.parse_math": False}

matplotlib.rcParams.update(STYLE)


class ReportFigure:
    """A chart of a report drawn as a vector image for the printed page, with the colours the screen and the spreadsheet paint the same series with."""

    def svg(self, plot: ReportPlot, locale: str) -> str:
        # A figure of its own, and never the global state of pyplot, because files are written on several threads at once.
        figure = Figure(figsize=(5.4, 3.0), layout="constrained", facecolor=SURFACE)
        axes = figure.add_subplot()
        colours = settings.charts.light

        if plot.kind in SLICED:
            self.slices(axes, plot, colours)
        else:
            self.marks(axes, plot, colours, locale)

        axes.set_title(plot.title, loc="left", color=INK, fontsize=10, pad=10)

        output = StringIO()
        figure.savefig(output, format="svg")
        drawn = output.getvalue()

        # The page carries the image inline, so whatever comes before the element itself is a declaration of a file it is no longer.
        return drawn[drawn.index("<svg") :]

    def marks(self, axes, plot: ReportPlot, colours: tuple[str, ...], locale: str):
        positions = range(len(plot.labels))
        width = 0.8 / len(plot.series)

        for index, series in enumerate(plot.series):
            colour = colours[index]
            shifted = [position - 0.4 + width * (index + 0.5) for position in positions]

            if plot.kind == ReportChartKind.COLUMN:
                axes.bar(shifted, series.values, width=width * 0.9, color=colour, linewidth=0, label=series.name)
            elif plot.kind == ReportChartKind.BAR:
                axes.barh(shifted, series.values, height=width * 0.9, color=colour, linewidth=0, label=series.name)
            elif plot.kind == ReportChartKind.LINE:
                axes.plot(positions, series.values, color=colour, linewidth=1.5, label=series.name)
            else:
                axes.fill_between(positions, series.values, color=colour, alpha=0.2, linewidth=0)
                axes.plot(positions, series.values, color=colour, linewidth=1.5, label=series.name)

        horizontal = plot.kind == ReportChartKind.BAR
        points = axes.yaxis if horizontal else axes.xaxis
        values = axes.xaxis if horizontal else axes.yaxis
        step = 1 if horizontal else math.ceil(len(plot.labels) / TICKS_MAX)

        points.set_major_locator(FixedLocator(list(positions)[::step]))
        points.set_major_formatter(FuncFormatter(lambda position, _: self.label(plot.labels, position)))
        values.set_major_formatter(FuncFormatter(lambda value, _: number(value, locale, 0 if float(value).is_integer() else 2)))

        # A count has no fraction, so an axis of whole numbers steps by whole numbers.
        if all(float(value).is_integer() for series in plot.series for value in series.values):
            values.set_major_locator(MaxNLocator(integer=True))

        # The first label of a bar chart is read first, so it is drawn on top.
        if horizontal:
            axes.invert_yaxis()

        axes.grid(axis="x" if horizontal else "y", color=GRID, linewidth=0.6)
        axes.set_axisbelow(True)
        axes.tick_params(colors=MUTED, labelcolor=MUTED, length=0)

        for side in ("top", "right", "left", "bottom"):
            axes.spines[side].set_visible(False)

        axes.spines["left" if horizontal else "bottom"].set_visible(True)
        axes.spines["left" if horizontal else "bottom"].set_color(BASELINE)

        # One series is named by the title, and more than one need a legend so none is told apart by its colour alone.
        if len(plot.series) > 1:
            axes.legend(frameon=False, labelcolor=SECONDARY)

    def slices(self, axes, plot: ReportPlot, colours: tuple[str, ...]):
        series = plot.series[0]
        hollow = {"width": 0.42} if plot.kind == ReportChartKind.DOUGHNUT else {}
        wedges, _ = axes.pie(series.values, colors=colours[: len(plot.labels)], startangle=90, counterclock=False, wedgeprops={"linewidth": 1.5 if len(plot.labels) > 1 else 0, "edgecolor": SURFACE, **hollow})

        axes.set_aspect("equal")
        axes.legend(wedges, [f"{label} · {shown}" for label, shown in zip(plot.labels, series.shown)], loc="center left", bbox_to_anchor=(1, 0.5), frameon=False, labelcolor=SECONDARY)

    def label(self, labels: tuple[str, ...], position: float) -> str:
        # The locator places a tick on a point and nowhere else, so every position is the index of a label.
        label = labels[round(position)]

        return label if len(label) <= LABEL_MAX else label[: LABEL_MAX - 1] + "…"


report_figure = ReportFigure()
