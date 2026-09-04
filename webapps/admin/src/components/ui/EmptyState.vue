<script setup>
import AppIcon from "./AppIcon.vue";

defineProps({
    icon: { type: String, default: "search" },
    message: { type: String, required: true },
});
</script>

<template>
    <div class="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <span class="flex size-12 items-center justify-center rounded-full bg-sunken text-ink-faint">
            <AppIcon :name="icon" :size="22" />
        </span>

        <p class="text-sm text-ink-muted">{{ message }}</p>

        <slot />
    </div>
</template>
