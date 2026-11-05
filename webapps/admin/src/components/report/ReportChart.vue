<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { useMetaStore } from "@/stores/meta";
import { useThemeStore } from "@/stores/theme";

const props = defineProps({
    plot: { type: Object, required: true },
});

const { locale } = useI18n();
const meta = useMetaStore();
const theme = useThemeStore();

const frame = ref(null);
const canvas = ref(null);

// The kinds where each label is a slice of one whole, which take one colour per label instead of one per series.
const SLICED = new Set(["pie", "doughnut"]);

// What each kind is drawn as, which is the chart type of the library and the axis its points are laid along.
const DRAWN = {
    column: { type: "bar", indexAxis: "x" },
    bar: { type: "bar", indexAxis: "y" },
    line: { type: "line", indexAxis: "x" },
    area: { type: "line", indexAxis: "x" },
    pie: { type: "pie", indexAxis: "x" },
    doughnut: { type: "doughnut", indexAxis: "x" },
};

// A line over this many points draws no marker on each, which would merge into a thicker line.
const MARKED_MAX = 31;

let chart = null;
let drawing = 0;

// The ink of the frame is read off the page, so the axis, the grid and the legend follow the palette the panel is drawn in right now.
function inks() {
    const styled = getComputedStyle(frame.value);

    return { muted: styled.color, line: styled.borderTopColor, surface: styled.backgroundColor };
}

function dataset(series, index, colours, ink) {
    if (SLICED.has(props.plot.kind)) {
        // A seam is what tells two slices apart, and a whole of one slice would draw it from the centre to the edge.
        return { label: series.name, data: series.values, backgroundColor: colours.slice(0, props.plot.labels.length), borderColor: ink.surface, borderWidth: props.plot.labels.length > 1 ? 2 : 0 };
    }

    const colour = colours[index];

    if (props.plot.kind === "line" || props.plot.kind === "area") {
        const marked = props.plot.labels.length <= MARKED_MAX;

        return { label: series.name, data: series.values, borderColor: colour, backgroundColor: `${colour}33`, borderWidth: 2, fill: props.plot.kind === "area" ? "origin" : false, pointRadius: marked ? 3 : 0, pointHoverRadius: 5 };
    }

    return { label: series.name, data: series.values, backgroundColor: colour, borderRadius: 4, borderSkipped: "start", maxBarThickness: 40 };
}

function configured(ink) {
    const colours = theme.dark ? meta.chartPalette.dark : meta.chartPalette.light;
    const { type, indexAxis } = DRAWN[props.plot.kind];
    const sliced = SLICED.has(props.plot.kind);
    const figures = new Intl.NumberFormat(locale.value);
    const axis = { ticks: { color: ink.muted }, grid: { color: ink.line }, border: { color: ink.line } };
    // A count has no fraction, so an axis of whole numbers steps by whole numbers.
    const whole = props.plot.series.every((series) => series.values.every(Number.isInteger));
    const valued = { ...axis, beginAtZero: true, ticks: { color: ink.muted, precision: whole ? 0 : undefined, callback: (value) => figures.format(value) } };

    // A tooltip says a value the way the table under the chart writes it, in the currency and the grouping of the reader.
    const tooltip = {
        callbacks: {
            label: (context) => {
                const shown = props.plot.series[context.datasetIndex].shown[context.dataIndex];

                return sliced ? `${context.label}: ${shown}` : `${context.dataset.label}: ${shown}`;
            },
        },
    };

    return {
        type,
        data: { labels: props.plot.labels, datasets: props.plot.series.map((series, index) => dataset(series, index, colours, ink)) },
        options: {
            indexAxis,
            maintainAspectRatio: false,
            interaction: { mode: sliced ? "nearest" : "index", intersect: sliced },
            plugins: {
                // One series is named by the title, and slices or several series need a legend so none is told apart by its colour alone.
                legend: { display: sliced || props.plot.series.length > 1, position: "bottom", labels: { color: ink.muted, boxWidth: 12 } },
                tooltip,
            },
            scales: scales(sliced, indexAxis, axis, valued),
        },
    };
}

// A slice has no axis, and the value axis is the one the points are not laid along.
function scales(sliced, indexAxis, axis, valued) {
    if (sliced) {
        return {};
    }

    return indexAxis === "y" ? { x: valued, y: axis } : { x: axis, y: valued };
}

async function draw() {
    const attempt = ++drawing;

    // The library is fetched the first time a chart is drawn, so a panel that never opens a report never downloads it.
    const { default: Chart } = await import("chart.js/auto");

    if (attempt !== drawing || !canvas.value) {
        return;
    }

    chart?.destroy();
    chart = new Chart(canvas.value, configured(inks()));
}

onMounted(draw);

watch(() => [props.plot, theme.dark, locale.value], draw);

onBeforeUnmount(() => {
    drawing += 1;
    chart?.destroy();
    chart = null;
});
</script>

<template>
    <figure ref="frame" class="m-0 border-line bg-raised text-ink-muted">
        <h2 class="mb-3 text-sm font-semibold text-ink">{{ props.plot.title }}</h2>

        <div class="relative h-64">
            <canvas ref="canvas" role="img" :aria-label="props.plot.title" />
        </div>
    </figure>
</template>
