<script setup>
import AppBoot from "@/components/layout/AppBoot.vue";
import ToastStack from "@/components/ui/ToastStack.vue";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
</script>

<template>
    <AppBoot v-if="ui.booting" />
    <RouterView v-else />
    <ToastStack />
</template>
