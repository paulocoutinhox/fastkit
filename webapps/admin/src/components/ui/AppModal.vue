<script setup>
import { onBeforeUnmount, watch } from "vue";

import AppIcon from "./AppIcon.vue";

const props = defineProps({
    open: { type: Boolean, default: false },
    title: { type: String, default: "" },
    wide: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

function onKeydown(event) {
    if (event.key === "Escape") {
        emit("close");
    }
}

watch(
    () => props.open,
    (open) => {
        document.body.classList.toggle("overflow-hidden", open);
        open ? window.addEventListener("keydown", onKeydown) : window.removeEventListener("keydown", onKeydown);
    },
);

onBeforeUnmount(() => {
    document.body.classList.remove("overflow-hidden");
    window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
    <Teleport to="body">
        <Transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
            <div v-if="open" class="fixed inset-0 z-40 flex items-end justify-center bg-inverse/50 p-4 sm:items-center" role="dialog" aria-modal="true" @click.self="emit('close')">
                <div class="w-full rounded-2xl bg-raised shadow-xl" :class="wide ? 'max-w-3xl' : 'max-w-lg'">
                    <header class="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
                        <h2 class="text-base font-semibold text-ink">{{ title }}</h2>

                        <button type="button" class="rounded-lg p-1 text-ink-faint transition hover:bg-sunken hover:text-ink-muted" :aria-label="$t('action.close')" @click="emit('close')">
                            <AppIcon name="close" :size="18" />
                        </button>
                    </header>

                    <div class="max-h-[70vh] overflow-y-auto px-5 py-4 text-sm text-ink-muted"><slot /></div>

                    <footer class="flex flex-col-reverse gap-2 border-t border-line px-5 py-4 sm:flex-row sm:justify-end">
                        <slot name="actions" />
                    </footer>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>
