<script setup>
import ReportCharts from "@/components/report/ReportCharts.vue";
import ReportTable from "@/components/report/ReportTable.vue";
import AppCard from "@/components/ui/AppCard.vue";
import EmptyState from "@/components/ui/EmptyState.vue";

const props = defineProps({
    result: { type: Object, required: true },
});
</script>

<template>
    <div class="space-y-5">
        <ReportCharts v-if="props.result.charts.length" :charts="props.result.charts" />

        <AppCard flush class="overflow-hidden">
            <p class="border-b border-line px-5 py-3 text-xs text-ink-muted lg:px-6">{{ $t("report.count", props.result.count) }}</p>

            <EmptyState v-if="!props.result.rows.length" :message="$t('report.empty')" />

            <ReportTable v-else :columns="props.result.columns" :rows="props.result.rows" />
        </AppCard>
    </div>
</template>
