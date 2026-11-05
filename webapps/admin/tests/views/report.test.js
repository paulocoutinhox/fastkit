import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory } from "vue-router";

import { answering } from "../helpers/api";
import { createTestRouter } from "../helpers/router";
import { api } from "@/api/client";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import { REPORTS } from "@/reports";
import { createAppRouter } from "@/router";
import { useAuthStore } from "@/stores/auth";
import { usePermissionsStore } from "@/stores/permissions";
import ReportView from "@/views/ReportView.vue";
import { flushPromises, mount } from "@vue/test-utils";

const DESCRIBED = {
    code: "purchases",
    title: "Purchases",
    formats: [
        { code: "pdf", label: "PDF" },
        { code: "excel", label: "Excel" },
    ],
    defaultFilter: { startsOn: "2026-10-10", endsOn: "2026-11-09" },
};

const RESULT = {
    columns: [
        { key: "reference", label: "Reference", kind: "text" },
        { key: "price", label: "Price", kind: "money" },
    ],
    rows: [
        { reference: "purchase-one", price: "USD 19.90" },
        { reference: "purchase-two", price: null },
    ],
    count: 2,
    charts: [],
    details: {},
};

async function opened(code, answers) {
    const router = createTestRouter(`/reports/${code}`);
    await router.isReady();

    vi.spyOn(api, "get").mockImplementation((path, params) => answers(path, params));

    const wrapper = mount(ReportView, { global: { plugins: [router] } });

    return { wrapper, router };
}

// An answer that has not come back yet, so a test can look at the screen while it is still waiting.
function pending() {
    let settle;
    const promise = new Promise((resolve, reject) => {
        settle = { resolve, reject };
    });

    return { promise, settle };
}

describe("ReportView", () => {
    it("lists the rows right away when the report opens on a filter of its own", async () => {
        const read = [];
        const { wrapper } = await opened("purchases", (path, params) => {
            read.push([path, params]);

            return Promise.resolve(path.endsWith("/rows") ? RESULT : DESCRIBED);
        });

        await flushPromises();

        expect(read[1]).toEqual(["/reports/purchases/rows", { startsOn: "2026-10-10", endsOn: "2026-11-09", status: null }]);
        expect(wrapper.text()).toContain("purchase-one");
        expect(wrapper.text()).toContain("USD 19.90");
        expect(wrapper.text()).toContain("2 rows");
        expect(wrapper.findAll("button").map((button) => button.text())).toEqual(expect.arrayContaining(["PDF", "Excel", "Apply the filter"]));
    });

    it("waits for a filter where the report has none of its own, and lists nothing until it is applied", async () => {
        const answered = { ...RESULT, details: { figures: [{ key: "accounts", label: "Accounts", value: 1234 }] } };
        const read = vi.fn((path) => Promise.resolve(path.endsWith("/rows") ? answered : { ...DESCRIBED, code: "subscriptions", formats: [], defaultFilter: null }));
        const { wrapper } = await opened("subscriptions", read);

        await flushPromises();

        expect(read).toHaveBeenCalledTimes(1);
        expect(wrapper.text()).toContain("Choose the filter and apply it to see the report.");

        await wrapper.find("form").trigger("submit");
        await flushPromises();
        await vi.dynamicImportSettled();
        await flushPromises();

        expect(read).toHaveBeenLastCalledWith("/reports/subscriptions/rows", { status: null, provider: null, startedFrom: null, startedUntil: null });
        expect(wrapper.text()).toContain("purchase-two");

        // The subscriptions draw a screen of their own, which puts the figures the report adds above the rows it shares with every other report.
        expect(wrapper.find("dl").text()).toContain("Accounts");
        expect(wrapper.find("dl").text()).toContain("1,234");
    });

    it("says it is preparing the report while it waits, and puts the alert in its place when the report fails", async () => {
        const rows = pending();
        const { wrapper } = await opened("purchases", (path) => (path.endsWith("/rows") ? rows.promise : Promise.resolve(DESCRIBED)));

        await flushPromises();

        expect(wrapper.find('[role="status"]').text()).toBe("Preparing the report…");
        expect(wrapper.text()).toContain("Preparing the report…");

        rows.settle.reject({ message: "Narrow the filter.", errors: { endsOn: "Too wide." } });
        await flushPromises();

        expect(wrapper.find('[role="status"]').text()).toBe("");
        expect(wrapper.text()).not.toContain("Preparing the report…");
        expect(wrapper.find('[role="alert"]').text()).toContain("Narrow the filter.");
        expect(wrapper.text()).toContain("Too wide.");
        expect(wrapper.text()).not.toContain("purchase-one");
    });

    it("hands the browser the file of the format that was asked for, with the filter on the screen, and lets its address go only after", async () => {
        vi.useFakeTimers({ toFake: ["setTimeout"] });

        const file = pending();
        const saved = [];
        const { wrapper } = await opened("purchases", (path) => Promise.resolve(path.endsWith("/rows") ? RESULT : DESCRIBED));
        const download = vi.spyOn(api, "download").mockReturnValue(file.promise);

        URL.createObjectURL = vi.fn(() => "blob:report");
        URL.revokeObjectURL = vi.fn();
        vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function () {
            saved.push(this.download);
        });

        await flushPromises();

        const excel = wrapper.findAll("button").find((button) => button.text() === "Excel");
        await excel.trigger("click");

        expect(download).toHaveBeenCalledWith("/reports/purchases/export/excel", { startsOn: "2026-10-10", endsOn: "2026-11-09", status: null });
        expect(wrapper.find('[role="status"]').text()).toBe("Preparing the file…");
        expect(wrapper.text()).toContain("purchase-one");

        file.settle.resolve({ blob: new Blob(["x"]), filename: "purchases-20261109-1200.xlsx" });
        await flushPromises();

        expect(saved).toEqual(["purchases-20261109-1200.xlsx"]);
        expect(URL.revokeObjectURL).not.toHaveBeenCalled();
        expect(wrapper.find('[role="status"]').text()).toBe("2 rows");

        vi.runAllTimers();
        vi.useRealTimers();

        expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:report");
    });

    it("says why a file could not be written", async () => {
        const { wrapper } = await opened("purchases", (path) => Promise.resolve(path.endsWith("/rows") ? RESULT : DESCRIBED));
        vi.spyOn(api, "download").mockRejectedValue({ message: "This filter selects too many rows." });

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text() === "PDF")
            .trigger("click");
        await flushPromises();

        expect(wrapper.find('[role="alert"]').text()).toContain("This filter selects too many rows.");
    });

    it("says why the report could not be opened", async () => {
        const { wrapper } = await opened("purchases", () => Promise.reject({ message: "This page does not exist." }));

        await flushPromises();

        expect(wrapper.find('[role="alert"]').text()).toContain("This page does not exist.");
        expect(wrapper.find("form").exists()).toBe(false);
    });

    it("never draws the answer of a report the screen already left", async () => {
        const rows = pending();
        const { wrapper, router } = await opened("purchases", (path) => {
            if (path === "/reports/purchases/rows") {
                return rows.promise;
            }

            return Promise.resolve(path === "/reports/subscriptions" ? { ...DESCRIBED, code: "subscriptions", defaultFilter: null } : DESCRIBED);
        });

        await flushPromises();
        await router.push("/reports/subscriptions");
        await flushPromises();

        rows.settle.resolve(RESULT);
        await flushPromises();

        expect(wrapper.text()).not.toContain("purchase-one");
        expect(wrapper.text()).toContain("Choose the filter and apply it to see the report.");
    });
});

describe("the reports of the menu", () => {
    it("names the reports the account reaches, under a section of their own", async () => {
        const router = createTestRouter("/");
        await router.isReady();

        usePermissionsStore().reports = ["subscriptions"];

        const wrapper = mount(AppSidebar, { global: { plugins: [router] } });
        const links = wrapper.findAll("a").map((link) => link.text());

        expect(wrapper.text()).toContain("Reports");
        expect(links).toContain("Subscriptions");
        expect(links).not.toContain("Purchases");
    });

    it("refuses the address of a report the account does not reach, and answers the one nobody wrote with the page that does not exist", async () => {
        answering([], {}, ["subscriptions"]);
        useAuthStore().apply("abc", { id: 1, username: "root" });

        const router = createAppRouter(createMemoryHistory());

        await router.push("/reports/purchases");
        expect(router.currentRoute.value.name).toBe("dashboard");

        await router.push("/reports/subscriptions");
        expect(router.currentRoute.value.name).toBe("report");

        await router.push("/reports/revenue");
        expect(router.currentRoute.value.name).toBe("not-found");
    });

    it("declares every report with an icon and a filter", () => {
        expect(REPORTS.every((report) => report.icon && report.filters.length)).toBe(true);
    });
});
