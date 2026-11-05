import { defineAsyncComponent } from "vue";

import { choice, date } from "@/resources/fields";

// A report may draw its result with a screen of its own, which receives the whole answer of the API: the rows, the charts and whatever details the report adds. Without one, the charts are drawn above the rows.

// Every report the panel draws, with the filter its screen asks for, which the API reads by the same code and the same names.
export const REPORTS = [
    {
        code: "purchases",
        icon: "card",
        filters: [date("startsOn", "field.startsOn", { required: true }), date("endsOn", "field.endsOn", { required: true }), choice("status", "field.status", "purchase_status")],
    },
    {
        code: "subscriptions",
        icon: "calendar",
        filters: [choice("status", "field.status", "subscription_status"), choice("provider", "field.provider", "provider"), date("startedFrom", "field.startedFrom"), date("startedUntil", "field.startedUntil")],
        view: defineAsyncComponent(() => import("@/reports/views/SubscriptionsReportView.vue")),
    },
];

const byCode = new Map(REPORTS.map((report) => [report.code, report]));

export function findReport(code) {
    return byCode.get(code) || null;
}
