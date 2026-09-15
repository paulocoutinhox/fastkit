<script setup>
import { ref, useId } from "vue";

import AppIcon from "./AppIcon.vue";
import { holdKeyboard } from "@/support/keyboard";

const props = defineProps({
    open: { type: Boolean, default: false },
    title: { type: String, default: "" },
    wide: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const titleId = useId();
const panel = ref(null);
const header = ref(null);

// The close button is the one control every dialog has, so what the dialog is about is focused before it.
holdKeyboard(
    () => props.open,
    panel,
    () => emit("close"),
    (reachable) => reachable.find((element) => !header.value.contains(element)) ?? reachable[0],
);
</script>

<template>
    <Teleport to="body">
        <Transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
            <div v-if="open" class="fixed inset-0 z-40 flex items-end justify-center bg-inverse/50 p-4 sm:items-center" role="dialog" aria-modal="true" :aria-labelledby="titleId" @click.self="emit('close')">
                <div ref="panel" class="w-full rounded-xl border border-line bg-raised shadow-xl" :class="wide ? 'max-w-3xl' : 'max-w-lg'">
                    <header ref="header" class="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
                        <h2 :id="titleId" class="text-base font-semibold text-ink">{{ title }}</h2>

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
