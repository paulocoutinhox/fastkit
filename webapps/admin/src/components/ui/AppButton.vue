<script setup>
import { computed, useSlots } from "vue";

import AppIcon from "./AppIcon.vue";

const VARIANTS = {
    primary: "bg-action text-action-ink hover:bg-action-strong focus-visible:outline-action",
    secondary: "bg-sunken text-ink ring-1 ring-line-strong hover:bg-lifted focus-visible:outline-ink-muted",
    danger: "bg-danger-fill text-white hover:bg-danger-fill-strong focus-visible:outline-danger-fill",
    ghost: "text-ink-muted hover:bg-sunken hover:text-ink focus-visible:outline-ink-muted",
};

const SIZES = {
    sm: "h-8 px-2.5 text-xs gap-1.5",
    md: "h-9 px-3.5 text-sm gap-2",
    lg: "h-10 px-4 text-sm gap-2",
};

const SQUARES = {
    sm: "size-8",
    md: "size-9",
    lg: "size-10",
};

const props = defineProps({
    // A label that opens a file picker is pressed like a button, and drawing it here is what keeps it one.
    as: { type: String, default: "button" },
    variant: { type: String, default: "primary" },
    size: { type: String, default: "md" },
    icon: { type: String, default: "" },
    type: { type: String, default: "button" },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
});

const slots = useSlots();

const isButton = computed(() => props.as === "button");

// A button that is working keeps its focus and refuses a second press, because a disabled one drops the focus of whoever pressed it to the page.
function held(event) {
    if (!props.loading) {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
}

const classes = computed(() => [
    "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg font-medium whitespace-nowrap transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
    VARIANTS[props.variant],
    slots.default ? SIZES[props.size] : SQUARES[props.size],
]);
</script>

<template>
    <component :is="as" :type="isButton ? type : undefined" :class="classes" :disabled="isButton ? disabled : undefined" :aria-busy="loading || undefined" @click.capture="held">
        <span v-if="loading" class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        <AppIcon v-else-if="icon" :name="icon" :size="size === 'sm' && $slots.default ? 14 : 16" />
        <slot />
    </component>
</template>
