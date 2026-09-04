<script setup>
defineProps({
    title: { type: String, default: "" },
    description: { type: String, default: "" },
});
</script>

<template>
    <section class="rounded-2xl bg-raised shadow-xs ring-1 ring-line">
        <header v-if="title || $slots.actions" class="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div class="min-w-0">
                <h2 class="text-sm font-semibold text-ink">{{ title }}</h2>
                <p v-if="description" class="mt-0.5 text-xs text-ink-muted">{{ description }}</p>
            </div>

            <div class="flex flex-wrap items-center gap-2"><slot name="actions" /></div>
        </header>

        <div :class="$slots.actions || title ? 'p-5' : 'p-5'"><slot /></div>
    </section>
</template>
