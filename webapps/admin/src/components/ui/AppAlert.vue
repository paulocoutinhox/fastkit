<script setup>
import { computed } from "vue";

import AppIcon from "./AppIcon.vue";

const TONES = {
    info: { classes: "bg-sky-50 text-sky-800 ring-sky-200", icon: "info" },
    success: { classes: "bg-good-soft text-good-ink ring-good-line", icon: "check" },
    warning: { classes: "bg-notice-soft text-notice ring-notice-soft", icon: "warning" },
    error: { classes: "bg-danger-soft text-danger-ink ring-danger-line", icon: "warning" },
};

const props = defineProps({
    tone: { type: String, default: "info" },
    title: { type: String, default: "" },
});

const tone = computed(() => TONES[props.tone]);
</script>

<template>
    <div class="flex gap-3 rounded-xl px-4 py-3 text-sm ring-1" :class="tone?.classes" role="alert">
        <AppIcon v-if="tone" :name="tone.icon" :size="18" class="mt-0.5 shrink-0" />

        <div class="min-w-0 flex-1">
            <p v-if="title" class="font-semibold">{{ title }}</p>
            <div class="break-words"><slot /></div>
        </div>
    </div>
</template>
