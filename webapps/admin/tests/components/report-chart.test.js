import { describe, expect, it, vi } from "vitest";

import ReportChart from "@/components/report/ReportChart.vue";
import ReportResult from "@/components/report/ReportResult.vue";
import { useMetaStore } from "@/stores/meta";
import { useThemeStore } from "@/stores/theme";
import { flushPromises, mount } from "@vue/test-utils";

// Every chart the library was asked to draw, so a test reads what was handed to it instead of pixels a test environment never paints.
const drawn = vi.hoisted(() => []);

vi.mock("chart.js/auto", () => ({
    default: class {
        constructor(canvas, config) {
            this.canvas = canvas;
            this.config = config;
            this.destroyed = false;
            drawn.push(this);
        }

        destroy() {
            this.destroyed = true;
        }
    },
}));

const LIGHT = ["#2a78d6", "#eb6834", "#1baf7a"];
const DARK = ["#3987e5", "#d95926", "#199e70"];

function plotted(kind, overrides = {}) {
    return { key: "paid", title: "Paid per day · USD", kind, labels: ["2026-11-01", "2026-11-02"], series: [{ name: "USD", values: [1200, 0], shown: ["USD 1,200.00", "USD 0.00"] }], ...overrides };
}

async function charted(plot) {
    drawn.length = 0;
    useMetaStore().chartPalette = { light: LIGHT, dark: DARK };

    const wrapper = mount(ReportChart, { props: { plot } });
    await flushPromises();

    return wrapper;
}

describe("ReportChart", () => {
    it("draws a column chart in the first colour, titled and named for a screen reader, and says each value the way the table writes it", async () => {
        const wrapper = await charted(plotted("column"));
        const { config } = drawn.at(-1);
        const tooltip = config.options.plugins.tooltip.callbacks.label;

        expect(wrapper.find("h2").text()).toBe("Paid per day · USD");
        expect(wrapper.find("canvas").attributes()).toMatchObject({ role: "img", "aria-label": "Paid per day · USD" });
        expect(config.type).toBe("bar");
        expect(config.options.indexAxis).toBe("x");
        expect(config.data.labels).toEqual(["2026-11-01", "2026-11-02"]);
        expect(config.data.datasets[0]).toMatchObject({ data: [1200, 0], backgroundColor: LIGHT[0], borderRadius: 4 });
        expect(config.options.plugins.legend.display).toBe(false);
        expect(tooltip({ datasetIndex: 0, dataIndex: 0, dataset: { label: "USD" } })).toBe("USD: USD 1,200.00");
        expect(config.options.scales.y.ticks.callback(1200)).toBe("1,200");
        expect(config.options.scales.y.ticks.precision).toBe(0);
    });

    it("lays a bar chart along the vertical axis and puts the values on the horizontal one", async () => {
        await charted(plotted("bar"));
        const { config } = drawn.at(-1);

        expect(config.options.indexAxis).toBe("y");
        expect(config.options.scales.x.beginAtZero).toBe(true);
        expect(config.options.scales.y.beginAtZero).toBeUndefined();
    });

    it("paints a slice per label and names them in a legend, because a slice is told apart by more than its colour", async () => {
        await charted(plotted("doughnut", { labels: ["Active", "Expired", "Trialing"], series: [{ name: "Count", values: [3, 2, 1], shown: ["3", "2", "1"] }] }));
        const { config } = drawn.at(-1);
        const tooltip = config.options.plugins.tooltip.callbacks.label;

        expect(config.type).toBe("doughnut");
        expect(config.data.datasets[0].backgroundColor).toEqual(LIGHT);
        expect(config.options.plugins.legend.display).toBe(true);
        expect(config.options.scales).toEqual({});
        expect(tooltip({ datasetIndex: 0, dataIndex: 1, label: "Expired" })).toBe("Expired: 2");
        expect(config.data.datasets[0].borderWidth).toBe(2);
    });

    it("draws a whole of one slice with no seam, and an axis of fractions with no whole steps forced on it", async () => {
        await charted(plotted("pie", { labels: ["Active"], series: [{ name: "Count", values: [3], shown: ["3"] }] }));
        const pie = drawn.at(-1).config;

        await charted(plotted("column", { series: [{ name: "USD", values: [0.5, 1.25], shown: ["USD 0.50", "USD 1.25"] }] }));
        const column = drawn.at(-1).config;

        expect(pie.data.datasets[0].borderWidth).toBe(0);
        expect(column.options.scales.y.ticks.precision).toBeUndefined();
    });

    it("fills an area under its line, and marks each point only while the points are few", async () => {
        await charted(plotted("area"));
        const area = drawn.at(-1).config;

        await charted(plotted("line", { labels: Array.from({ length: 40 }, (_, day) => `d${day}`), series: [{ name: "Count", values: Array(40).fill(1), shown: Array(40).fill("1") }] }));
        const line = drawn.at(-1).config;

        expect(area.type).toBe("line");
        expect(area.data.datasets[0]).toMatchObject({ fill: "origin", pointRadius: 3 });
        expect(line.data.datasets[0]).toMatchObject({ fill: false, pointRadius: 0 });
    });

    it("draws several series with a legend, each in the colour of its own slot", async () => {
        await charted(
            plotted("column", {
                series: [
                    { name: "New", values: [1, 2], shown: ["1", "2"] },
                    { name: "Renewed", values: [3, 4], shown: ["3", "4"] },
                ],
            }),
        );
        const { config } = drawn.at(-1);

        expect(config.data.datasets.map((dataset) => dataset.backgroundColor)).toEqual([LIGHT[0], LIGHT[1]]);
        expect(config.options.plugins.legend.display).toBe(true);
    });

    it("draws again in the colours of the dark palette when the panel turns dark, and lets the chart it drew before go", async () => {
        await charted(plotted("column"));
        const before = drawn.at(-1);

        useThemeStore().chosen = "dark";
        await flushPromises();

        expect(before.destroyed).toBe(true);
        expect(drawn.at(-1).config.data.datasets[0].backgroundColor).toBe(DARK[0]);

        useThemeStore().chosen = "system";
    });

    it("lets its chart go when the screen leaves, so nothing keeps listening on a canvas that is gone", async () => {
        const wrapper = await charted(plotted("column"));
        const chart = drawn.at(-1);

        wrapper.unmount();

        expect(chart.destroyed).toBe(true);
    });
});

describe("ReportResult", () => {
    it("draws the charts above the rows", async () => {
        drawn.length = 0;
        useMetaStore().chartPalette = { light: LIGHT, dark: DARK };

        const result = { columns: [{ key: "reference", label: "Reference", kind: "text" }], rows: [{ reference: "purchase-one" }], count: 1, charts: [plotted("column")], details: {} };
        const wrapper = mount(ReportResult, { props: { result } });
        await flushPromises();

        const html = wrapper.html();

        expect(drawn).toHaveLength(1);
        expect(html.indexOf("Paid per day · USD")).toBeLessThan(html.indexOf("purchase-one"));
    });

    it("draws no chart where the report answers none", async () => {
        drawn.length = 0;

        const wrapper = mount(ReportResult, { props: { result: { columns: [], rows: [], count: 0, charts: [], details: {} } } });
        await flushPromises();

        expect(drawn).toHaveLength(0);
        expect(wrapper.find("canvas").exists()).toBe(false);
        expect(wrapper.text()).toContain("No row matches this filter.");
    });
});
