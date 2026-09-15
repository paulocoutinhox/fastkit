<script setup>
import { ref } from "vue";

import AppSidebar from "./AppSidebar.vue";
import AppTopbar from "./AppTopbar.vue";
import { useUiStore } from "@/stores/ui";
import { holdKeyboard } from "@/support/keyboard";

const ui = useUiStore();
const drawer = ref(null);

// The menu of a narrow screen covers the page, so it holds the keyboard the way a dialog does.
holdKeyboard(
    () => ui.sidebarOpen,
    drawer,
    () => ui.toggleSidebar(false),
);
</script>

<template>
    <div class="flex h-full overflow-hidden">
        <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-action focus:px-3 focus:py-2 focus:text-sm focus:text-action-ink">{{ $t("action.skipToContent") }}</a>

        <div class="hidden lg:block"><AppSidebar /></div>

        <Transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
            <div v-if="ui.sidebarOpen" class="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" :aria-label="$t('common.menu')">
                <div class="absolute inset-0 bg-inverse/50" @click="ui.toggleSidebar(false)" />
                <div ref="drawer" class="absolute inset-y-0 left-0"><AppSidebar /></div>
            </div>
        </Transition>

        <!-- The min-h-0 class is what lets the column shrink below its content, so main owns the scroll and the page never grows past the viewport. -->
        <div class="flex min-h-0 min-w-0 flex-1 flex-col">
            <AppTopbar>
                <slot name="header" />
            </AppTopbar>

            <!-- The relative class keeps the absolutely positioned sr-only elements anchored here instead of the page, which would grow the document. -->
            <main id="content" tabindex="-1" class="relative min-h-0 flex-1 overflow-y-auto px-4 py-5 lg:px-8 lg:py-6">
                <div class="space-y-5"><slot /></div>
            </main>

            <!-- The bar stands outside the scroll, so what a screen asks to be pressed is in reach however long the screen is, and it keeps one row on a phone by drawing the lesser buttons as their icon. -->
            <div v-if="$slots.actions" class="relative flex items-center justify-between gap-2 border-t border-line bg-surface px-4 py-3 lg:px-8">
                <slot name="actions" />
            </div>
        </div>
    </div>
</template>
