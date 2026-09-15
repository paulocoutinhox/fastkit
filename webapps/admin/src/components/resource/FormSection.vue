<script setup>
defineProps({
    title: { type: String, required: true },
});
</script>

<template>
    <!-- The title stands in a column of its own on a wide screen, so the groups read as a list of headings and the fields take every column that is left. -->
    <div class="grid gap-4 px-5 py-6 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-10 lg:px-6 xl:grid-cols-[16rem_minmax(0,1fr)]">
        <h2 class="text-sm font-semibold text-ink">{{ title }}</h2>

        <div class="min-w-0"><slot /></div>
    </div>
</template>
