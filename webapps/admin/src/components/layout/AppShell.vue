<script setup>
import AppSidebar from "./AppSidebar.vue";
import AppTopbar from "./AppTopbar.vue";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
</script>

<template>
    <div class="flex h-full overflow-hidden">
        <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-brand-600 focus:px-3 focus:py-2 focus:text-sm focus:text-white">{{ $t("action.skipToContent") }}</a>

        <div class="hidden lg:block"><AppSidebar /></div>

        <Transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
            <div v-if="ui.sidebarOpen" class="fixed inset-0 z-30 lg:hidden">
                <div class="absolute inset-0 bg-inverse/50" @click="ui.toggleSidebar(false)" />
                <div class="absolute inset-y-0 left-0"><AppSidebar /></div>
            </div>
        </Transition>

        <!-- min-h-0 is what lets the column shrink below its content, so main owns the scroll and the page never grows past the viewport -->
        <div class="flex min-h-0 min-w-0 flex-1 flex-col">
            <AppTopbar>
                <slot name="header" />
            </AppTopbar>

            <!-- relative keeps the absolutely positioned sr-only elements anchored here instead of the page, which would grow the document -->
            <main id="content" class="relative min-h-0 flex-1 overflow-y-auto p-4 lg:p-6">
                <div class="mx-auto max-w-7xl space-y-6"><slot /></div>
            </main>
        </div>
    </div>
</template>
