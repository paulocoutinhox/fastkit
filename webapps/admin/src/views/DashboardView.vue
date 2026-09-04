<script setup>
import { computed, onMounted, ref } from "vue";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import AppBadge from "@/components/ui/AppBadge.vue";
import AppIcon from "@/components/ui/AppIcon.vue";
import { RESOURCES } from "@/resources";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";

const meta = useMetaStore();
const permissions = usePermissionsStore();

// What the panel counts first when the account reaches it, and everything else it reaches follows in the order it is declared.
const PREFERRED = ["tenants", "users", "products", "subscriptions", "plans", "app-events"];

const TILE_LIMIT = 6;

function rank(resource) {
    const preferred = PREFERRED.indexOf(resource.name);

    return preferred === -1 ? PREFERRED.length : preferred;
}

const counts = ref({});
const loading = ref(true);

// A tile of something this account cannot read would be a card that answers 403, and an account that reaches none of the usual ones still has a dashboard.
const tiles = computed(() =>
    RESOURCES.filter((resource) => !resource.managedByParent && permissions.reaches(resource.name))
        .sort((first, second) => rank(first) - rank(second))
        .slice(0, TILE_LIMIT)
        .map((resource) => ({ resource: resource.name, icon: resource.icon })),
);

onMounted(async () => {
    const payloads = await Promise.all(tiles.value.map((tile) => api.get(`/${tile.resource}`, { limit: 1 }).catch(() => null)));

    counts.value = Object.fromEntries(tiles.value.map((tile, index) => [tile.resource, payloads[index] ? payloads[index].count : "—"]));
    loading.value = false;
});
</script>

<template>
    <AppShell>
        <template #header>
            <div>
                <h1 class="text-base font-semibold text-ink">{{ $t("dashboard.title") }}</h1>
                <p class="truncate text-xs text-ink-muted">{{ $t("dashboard.subtitle") }}</p>
            </div>
        </template>

        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <RouterLink v-for="tile in tiles" :key="tile.resource" :to="{ name: 'resource-list', params: { resource: tile.resource } }" class="flex items-center gap-4 rounded-2xl bg-raised p-5 shadow-xs ring-1 ring-line transition hover:ring-brand-300">
                <span class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-ink"><AppIcon :name="tile.icon" :size="20" /></span>

                <div class="min-w-0">
                    <p class="truncate text-sm text-ink-muted">{{ $t(`resource.${tile.resource}.title`) }}</p>
                    <p class="text-2xl font-semibold text-ink tabular-nums">{{ loading ? "—" : counts[tile.resource] }}</p>
                </div>
            </RouterLink>
        </div>

        <div class="flex flex-wrap items-center gap-3 rounded-2xl bg-raised p-5 text-sm text-ink-muted shadow-xs ring-1 ring-line">
            <span>{{ $t("dashboard.environment") }}</span>
            <AppBadge :tone="meta.environment === 'prod' ? 'error' : 'info'">{{ meta.environment }}</AppBadge>

            <span class="ml-4">{{ $t("dashboard.storage") }}</span>
            <code class="rounded bg-sunken px-1.5 py-0.5 font-mono text-xs">{{ meta.storageBaseUrl }}</code>
        </div>
    </AppShell>
</template>
