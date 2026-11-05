<script setup>
import { computed } from "vue";

import AppButton from "@/components/ui/AppButton.vue";
import { useMetaStore } from "@/stores/meta";

const props = defineProps({ next: { type: String, default: "/" }, disabled: { type: Boolean, default: false } });
const meta = useMetaStore();
const methods = computed(() => meta.authentication.social);

function address(provider) {
    const query = new URLSearchParams({ surface: "admin", next: props.next });

    return `/account/social/${provider}/start?${query}`;
}
</script>

<template>
    <section v-if="methods.length" class="space-y-3 rounded-xl border border-line bg-raised p-6 shadow-sm">
        <h2 class="text-base font-semibold text-ink">{{ $t("auth.socialTitle") }}</h2>
        <AppButton v-for="method in methods" :key="method.provider" as="a" :href="address(method.provider)" variant="secondary" class="w-full" :disabled="disabled">{{ $t("auth.continueWith", { provider: method.label }) }}</AppButton>
    </section>
</template>
