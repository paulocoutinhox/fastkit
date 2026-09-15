<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

import AppIcon from "../ui/AppIcon.vue";
import AppLogo from "../ui/AppLogo.vue";
import { SECTIONS, arranged, resourcesOfSection } from "@/resources";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";

const BASE = "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition";
const IDLE = "text-ink-muted hover:bg-lifted/60 hover:text-ink";
const CURRENT = "bg-lifted font-medium text-ink";

const route = useRoute();
const { t, locale } = useI18n();
const meta = useMetaStore();
const permissions = usePermissionsStore();

// A section draws what this account reaches, and one that reaches nothing in it is not a heading over an empty list.
// The order is the one the product declares, and alphabetical reads the names in the language of the panel.
const sections = computed(() =>
    arranged(
        SECTIONS.map((section) => ({
            key: section,
            label: t(`section.${section}`),
            resources: arranged(
                resourcesOfSection(section)
                    .filter((resource) => permissions.reaches(resource.name))
                    .map((resource) => ({ ...resource, label: t(`resource.${resource.name}.menu`) })),
                locale.value,
            ),
        })).filter((section) => section.resources.length),
        locale.value,
    ),
);

// The resource of the route is what marks the item, so viewing or editing a record keeps the menu where it is.
function isCurrent(name) {
    return route.params.resource === name;
}
</script>

<template>
    <aside class="flex h-full w-64 flex-col border-r border-line bg-sidebar">
        <div class="flex items-center gap-3 px-5 py-4">
            <AppLogo size="menu" />

            <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-ink">{{ meta.name }}</p>
                <p class="truncate text-xs text-ink-faint">v{{ meta.version }}</p>
            </div>
        </div>

        <!-- The min-h-0 class is what lets the menu shrink below its content, so it scrolls on its own instead of stretching the page. -->
        <nav class="scrollbar-hidden min-h-0 flex-1 space-y-5 overflow-y-auto px-3 pb-6">
            <div class="space-y-0.5">
                <RouterLink :to="{ name: 'dashboard' }" :class="[BASE, route.name === 'dashboard' ? CURRENT : IDLE]" :aria-current="route.name === 'dashboard' ? 'page' : undefined">
                    <AppIcon name="dashboard" :size="18" />
                    {{ $t("common.dashboard") }}
                </RouterLink>

                <!-- The bar at the top has no room for the picture on a phone, and this is where a phone navigates from. -->
                <RouterLink :to="{ name: 'profile' }" :class="[BASE, route.name === 'profile' ? CURRENT : IDLE]" :aria-current="route.name === 'profile' ? 'page' : undefined">
                    <AppIcon name="user" :size="18" />
                    {{ $t("profile.title") }}
                </RouterLink>
            </div>

            <div v-for="section in sections" :key="section.key">
                <p class="px-3 pb-1.5 text-xs font-medium text-ink-faint">{{ section.label }}</p>

                <ul class="space-y-0.5">
                    <li v-for="resource in section.resources" :key="resource.name">
                        <RouterLink :to="{ name: 'resource-list', params: { resource: resource.name } }" :class="[BASE, isCurrent(resource.name) ? CURRENT : IDLE]" :aria-current="isCurrent(resource.name) ? 'page' : undefined">
                            <AppIcon :name="resource.icon" :size="18" class="shrink-0" />
                            <span class="truncate">{{ resource.label }}</span>
                        </RouterLink>
                    </li>
                </ul>
            </div>
        </nav>
    </aside>
</template>
