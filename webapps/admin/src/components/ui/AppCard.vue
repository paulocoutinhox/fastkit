<script setup>
defineProps({
    // A body made of rows that divide themselves reaches the border, where padding would leave every divider short of it.
    flush: { type: Boolean, default: false },
});
</script>

<template>
    <section class="rounded-xl border border-line bg-raised" :class="flush ? '' : 'p-5'">
        <slot />
    </section>
</template>
