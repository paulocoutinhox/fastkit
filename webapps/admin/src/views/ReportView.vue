<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import ReportResult from "@/components/report/ReportResult.vue";
import FieldGroup from "@/components/resource/FieldGroup.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import { findReport } from "@/reports";
import { saveFile } from "@/support/download";
import { provideHolds } from "@/support/holds";
import { newest } from "@/support/latest";
import { pointAt } from "@/support/refusal";

const route = useRoute();
const { t } = useI18n();

const report = computed(() => findReport(route.params.report));
const group = computed(() => ({ key: "filter", fields: report.value.filters }));

// The screen the result is drawn with, which is the report's own where it declares one.
const view = computed(() => report.value.view || ReportResult);

const described = ref(null);
const values = ref({});
const errors = ref({});
const failure = ref("");
const result = ref(null);

// What the screen is doing right now, which is what draws the indicator: reading what the report is, preparing its rows, or writing one of its files.
const working = ref("");
const form = ref(null);
const holds = provideHolds();

const answers = newest();

const busy = computed(() => working.value !== "");
const preparing = computed(() => working.value === "describing" || working.value === "running");
const exporting = computed(() => working.value.startsWith("export-"));

// One region is always on the page and only its words change, because a region drawn already holding its words is announced by some readers and not by others, and the one that answers nothing would never say the rows came back.
const announcement = computed(() => {
    if (working.value === "running") {
        return t("report.running");
    }

    if (exporting.value) {
        return t("report.exporting");
    }

    if (result.value) {
        return result.value.rows.length ? t("report.count", result.value.count) : t("report.empty");
    }

    return "";
});

function emptied() {
    return Object.fromEntries(report.value.filters.map((field) => [field.name, null]));
}

function onChange(name, value) {
    values.value = { ...values.value, [name]: value };
}

// A refusal is always said above the filter, and the fields it names are marked as well, so an indicator that stops is never followed by nothing.
function refused(error) {
    errors.value = error.errors || {};
    failure.value = error.message;
}

async function describe() {
    const attempt = answers.take();
    described.value = null;
    result.value = null;
    errors.value = {};
    failure.value = "";
    values.value = emptied();
    working.value = "describing";

    try {
        const answer = await api.get(`/reports/${report.value.code}`);

        if (answers.stale(attempt)) {
            return;
        }

        described.value = answer;
        working.value = "";

        // A report that opens on a filter of its own lists its rows right away, and one that does not waits for the operator to choose.
        if (answer.defaultFilter) {
            values.value = { ...values.value, ...answer.defaultFilter };
            await apply();
        }
    } catch (error) {
        if (!answers.stale(attempt)) {
            failure.value = error.message;
            working.value = "";
        }
    }
}

async function apply() {
    if (busy.value || holds.size > 0) {
        return;
    }

    const attempt = answers.take();
    working.value = "running";
    errors.value = {};
    failure.value = "";

    try {
        const answer = await api.get(`/reports/${report.value.code}/rows`, values.value);

        if (!answers.stale(attempt)) {
            result.value = answer;
        }
    } catch (error) {
        if (!answers.stale(attempt)) {
            result.value = null;
            refused(error);
            await pointAt(form.value);
        }
    } finally {
        if (!answers.stale(attempt)) {
            working.value = "";
        }
    }
}

async function exportAs(format) {
    if (busy.value || holds.size > 0) {
        return;
    }

    const attempt = answers.take();
    working.value = `export-${format.code}`;
    errors.value = {};
    failure.value = "";

    try {
        const file = await api.download(`/reports/${report.value.code}/export/${format.code}`, values.value);

        if (!answers.stale(attempt)) {
            saveFile(file);
        }
    } catch (error) {
        if (!answers.stale(attempt)) {
            refused(error);
            await pointAt(form.value);
        }
    } finally {
        if (!answers.stale(attempt)) {
            working.value = "";
        }
    }
}

onBeforeUnmount(() => answers.take());

watch(() => route.params.report, describe, { immediate: true });
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t(`report.${report.code}.title`) }}</h1>
        </template>

        <p role="status" class="sr-only">{{ announcement }}</p>

        <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

        <form v-if="described" id="report-filter" ref="form" @submit.prevent="apply">
            <AppCard flush>
                <FieldGroup :group="group" :values="values" :fields="report.filters" :errors="errors" @change="onChange" />
            </AppCard>
        </form>

        <AppCard v-if="preparing" flush>
            <div aria-hidden="true" class="flex items-center justify-center gap-3 px-6 py-16 text-sm text-ink-muted">
                <span class="size-4 animate-spin rounded-full border-2 border-line-strong border-t-ink" />
                {{ working === "running" ? $t("report.running") : $t("common.loading") }}
            </div>
        </AppCard>

        <template v-else-if="described">
            <AppCard v-if="exporting" flush>
                <p aria-hidden="true" class="flex items-center gap-2 px-5 py-3 text-xs text-ink-muted lg:px-6">
                    <span class="size-3.5 animate-spin rounded-full border-2 border-line-strong border-t-ink" />
                    {{ $t("report.exporting") }}
                </p>
            </AppCard>

            <component :is="view" v-if="result" :result="result" />

            <AppCard v-else flush>
                <EmptyState icon="chart" :message="$t('report.idle')" />
            </AppCard>
        </template>

        <template v-if="described" #actions>
            <div class="flex flex-wrap gap-2">
                <!-- Every format downloads with the same icon, so on a phone the button says its format, the icon gives way and the padding narrows to keep the bar one row. -->
                <AppButton v-for="format in described.formats" :key="format.code" variant="secondary" icon="download" class="max-sm:px-2.5 max-sm:[&>svg]:hidden" :loading="working === `export-${format.code}`" :disabled="holds.size > 0 || (busy && working !== `export-${format.code}`)" @click="exportAs(format)">{{
                    format.label
                }}</AppButton>
            </div>

            <AppButton type="submit" form="report-filter" icon="search" :loading="working === 'running'" :disabled="holds.size > 0 || (busy && working !== 'running')">{{ $t("report.apply") }}</AppButton>
        </template>
    </AppShell>
</template>
