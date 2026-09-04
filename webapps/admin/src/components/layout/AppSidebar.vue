<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import AppIcon from "../ui/AppIcon.vue";
import { SECTIONS, resourcesOfSection } from "@/resources";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";

const BASE = "flex items-center gap-3 rounded-lg border-l-2 px-3 py-2 text-sm transition";
const IDLE = "border-transparent hover:bg-inverse hover:text-white";
const CURRENT = "border-brand-500 bg-inverse font-medium text-white [&>svg]:text-brand-400";

const route = useRoute();
const meta = useMetaStore();
const permissions = usePermissionsStore();
const ui = useUiStore();

// A section draws what this account reaches, and one that reaches nothing in it is not a heading over an empty list.
const sections = computed(() => SECTIONS.map((section) => ({ key: section, resources: resourcesOfSection(section).filter((resource) => permissions.reaches(resource.name)) })).filter((section) => section.resources.length));

// The resource of the route is what marks the item, so viewing or editing a record keeps the menu where it is.
function classesFor(name) {
    return [BASE, route.params.resource === name ? CURRENT : IDLE];
}
</script>

<template>
    <aside class="flex h-full w-72 flex-col bg-inverse text-ink-faint">
        <div class="flex items-center gap-3 px-5 py-5">
            <span class="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white"><AppIcon name="bolt" :size="18" /></span>

            <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-white">{{ meta.name }}</p>
                <p class="truncate text-xs text-ink-faint">v{{ meta.version }}</p>
            </div>
        </div>

        <!-- min-h-0 is what lets the menu shrink below its content, so it scrolls on its own instead of stretching the page -->
        <nav class="scrollbar-hidden min-h-0 flex-1 space-y-6 overflow-y-auto px-3 pb-6">
            <RouterLink :to="{ name: 'dashboard' }" :class="[BASE, route.name === 'dashboard' ? CURRENT : IDLE]" @click="ui.toggleSidebar(false)">
                <AppIcon name="dashboard" :size="18" />
                {{ $t("common.dashboard") }}
            </RouterLink>

            <div v-for="section in sections" :key="section.key">
                <p class="px-3 pb-2 text-xs font-semibold tracking-wider text-ink-muted uppercase">{{ $t(`section.${section.key}`) }}</p>

                <ul class="space-y-0.5">
                    <li v-for="resource in section.resources" :key="resource.name">
                        <RouterLink :to="{ name: 'resource-list', params: { resource: resource.name } }" :class="classesFor(resource.name)" @click="ui.toggleSidebar(false)">
                            <AppIcon :name="resource.icon" :size="18" class="shrink-0 text-ink-muted" />
                            <span class="truncate">{{ $t(`resource.${resource.name}.menu`) }}</span>
                        </RouterLink>
                    </li>
                </ul>
            </div>
        </nav>
    </aside>
</template>
