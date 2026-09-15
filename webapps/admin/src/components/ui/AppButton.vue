<script setup>
import { computed } from "vue";

import AppIcon from "./AppIcon.vue";

const VARIANTS = {
    primary: "bg-brand-600 text-white shadow-sm hover:bg-brand-700 focus-visible:outline-brand-600",
    secondary: "bg-raised text-ink-soft ring-1 ring-line-strong shadow-xs hover:bg-sunken focus-visible:outline-ink-muted",
    danger: "bg-danger-fill text-white shadow-sm hover:bg-danger-fill-strong focus-visible:outline-danger-fill",
    ghost: "text-ink-muted hover:bg-sunken focus-visible:outline-ink-muted",
};

const SIZES = {
    sm: "px-2.5 py-1.5 text-xs gap-1.5",
    md: "px-3.5 py-2 text-sm gap-2",
    lg: "px-4 py-2.5 text-sm gap-2",
};

const props = defineProps({
    variant: { type: String, default: "primary" },
    size: { type: String, default: "md" },
    icon: { type: String, default: "" },
    type: { type: String, default: "button" },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
});

const classes = computed(() => ["inline-flex items-center justify-center rounded-lg font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60", VARIANTS[props.variant], SIZES[props.size]]);
</script>

<template>
    <button :type="type" :class="classes" :disabled="disabled || loading">
        <span v-if="loading" class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        <AppIcon v-else-if="icon" :name="icon" :size="size === 'sm' ? 14 : 16" />
        <slot />
    </button>
</template>
