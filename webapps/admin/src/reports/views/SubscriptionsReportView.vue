<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import ReportResult from "@/components/report/ReportResult.vue";

const props = defineProps({
    result: { type: Object, required: true },
});

const { locale } = useI18n();

const figures = computed(() => new Intl.NumberFormat(locale.value));
</script>

<template>
    <div class="space-y-5">
        <dl class="grid gap-5 sm:grid-cols-3">
            <!-- A list of terms holds its pairs directly or in a div, so each figure is drawn as a card without being the section a card is. -->
            <div v-for="figure in props.result.details.figures" :key="figure.key" class="rounded-xl border border-line bg-raised p-5">
                <dt class="text-xs font-medium tracking-wide text-ink-muted uppercase">{{ figure.label }}</dt>
                <dd class="mt-1 text-2xl font-semibold text-ink tabular-nums">{{ figures.format(figure.value) }}</dd>
            </div>
        </dl>

        <ReportResult :result="props.result" />
    </div>
</template>
