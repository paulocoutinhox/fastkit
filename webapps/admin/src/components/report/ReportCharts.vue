<script setup>
import ReportChart from "@/components/report/ReportChart.vue";
import AppCard from "@/components/ui/AppCard.vue";

const props = defineProps({
    charts: { type: Array, required: true },
});
</script>

<template>
    <div class="grid gap-5 xl:grid-cols-2">
        <AppCard v-for="plot in props.charts" :key="plot.key">
            <ReportChart :plot="plot" />
        </AppCard>
    </div>
</template>
