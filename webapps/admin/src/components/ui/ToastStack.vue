<script setup>
import AppIcon from "./AppIcon.vue";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();

const TONES = {
    success: { classes: "bg-good-fill", icon: "check" },
    error: { classes: "bg-danger-fill", icon: "warning" },
    info: { classes: "bg-inverse", icon: "info" },
};
</script>

<template>
    <div class="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:items-end" role="status" aria-live="polite">
        <TransitionGroup enter-active-class="transition duration-200" enter-from-class="translate-y-2 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-2 opacity-0">
            <div v-for="toast in ui.toasts" :key="toast.id" class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl px-4 py-3 text-sm text-white shadow-lg" :class="TONES[toast.tone].classes">
                <AppIcon :name="TONES[toast.tone].icon" :size="18" class="mt-0.5 shrink-0" />

                <p class="min-w-0 flex-1 break-words">{{ toast.message }}</p>

                <button type="button" class="shrink-0 opacity-70 transition hover:opacity-100" :aria-label="$t('action.close')" @click="ui.dismiss(toast.id)">
                    <AppIcon name="close" :size="16" />
                </button>
            </div>
        </TransitionGroup>
    </div>
</template>
