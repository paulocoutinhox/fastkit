<script setup>
// The three places the panel draws its mark, indexed so a size nobody declared draws nothing instead of the wrong one.
const SIZES = { menu: "size-8", entry: "size-10", boot: "size-14" };

defineProps({
    size: { type: String, required: true },
});
</script>

<template>
    <!-- One drawing for both palettes: the tile is the colour of the text and the bolt the colour of the page, so it is black on the light side and light on the dark one. -->
    <svg viewBox="0 0 512 512" class="shrink-0" :class="SIZES[size]" aria-hidden="true">
        <rect width="512" height="512" rx="116" class="fill-ink" />
        <path d="M310 88 160 288a10 10 0 0 0 8 16h64l-30 120 150-200a10 10 0 0 0-8-16h-64z" class="fill-surface" />
    </svg>
</template>
