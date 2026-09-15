<script setup>
import { computed } from "vue";

const TONES = {
    neutral: "bg-sunken text-ink-soft ring-line",
    success: "bg-good-soft text-good-ink ring-good-line",
    warning: "bg-notice-soft text-notice ring-notice-soft",
    error: "bg-danger-soft text-danger-ink ring-danger-line",
    info: "bg-info-soft text-info-ink ring-info-line",
    brand: "bg-brand-soft text-brand-ink ring-brand-line",
};

const props = defineProps({
    tone: { type: String, default: "neutral" },
});

const classes = computed(() => TONES[props.tone]);
</script>

<template>
    <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap" :class="classes">
        <slot />
    </span>
</template>
