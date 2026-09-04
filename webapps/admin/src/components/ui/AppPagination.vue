<script setup>
import { computed } from "vue";

import AppButton from "./AppButton.vue";

const props = defineProps({
    count: { type: Number, required: true },
    limit: { type: Number, required: true },
    offset: { type: Number, required: true },
});

const emit = defineEmits(["change"]);

const totalPages = computed(() => Math.max(1, Math.ceil(props.count / props.limit)));
const currentPage = computed(() => Math.floor(props.offset / props.limit) + 1);

function go(page) {
    emit("change", (page - 1) * props.limit);
}
</script>

<template>
    <div class="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 text-xs text-ink-muted">
        <p>{{ $t("common.results", { count }) }}</p>

        <div class="flex items-center gap-2">
            <span>{{ $t("common.page", { current: currentPage, total: totalPages }) }}</span>

            <AppButton variant="secondary" size="sm" icon="chevronLeft" :disabled="currentPage <= 1" @click="go(currentPage - 1)" />
            <AppButton variant="secondary" size="sm" icon="chevronRight" :disabled="currentPage >= totalPages" @click="go(currentPage + 1)" />
        </div>
    </div>
</template>
