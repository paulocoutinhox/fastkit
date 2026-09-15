<script setup>
import { computed } from "vue";

import { nameOf } from "@/support/naming";

// The two places this panel draws an account, indexed so a name nobody declared draws nothing instead of the wrong size.
const SIZES = { topbar: "size-8 text-xs", profile: "size-20 text-2xl" };

const props = defineProps({
    user: { type: Object, default: null },
    size: { type: String, default: "topbar" },
});

const named = computed(() => nameOf(props.user));

// A picture is what an account chose to be known by, and what it has instead is the name it is known by.
const initials = computed(
    () =>
        (named.value || "?")
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((word) => word[0])
            .join("")
            .toUpperCase() || "?",
);
</script>

<template>
    <img v-if="user?.avatarUrl" :src="user.avatarUrl" :alt="named" class="shrink-0 rounded-full object-cover ring-1 ring-line" :class="SIZES[size]" />
    <span v-else class="flex shrink-0 items-center justify-center rounded-full bg-brand-600 font-semibold text-white" :class="SIZES[size]">{{ initials }}</span>
</template>
