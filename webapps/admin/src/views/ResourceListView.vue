<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import DeleteConfirm from "@/components/resource/DeleteConfirm.vue";
import ResourceFilters from "@/components/resource/ResourceFilters.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import AppPagination from "@/components/ui/AppPagination.vue";
import DataGrid from "@/components/ui/DataGrid.vue";
import { canCreate, canDelete, canEdit, canView, defaultOrdering, findResource, gridColumns, labelOf } from "@/resources";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import { dependentsOf } from "@/support/dependencies";
import { newest } from "@/support/latest";

const SEARCH_DELAY = 300;
const PAGE_SIZE = 25;

const route = useRoute();
const router = useRouter();
const permissions = usePermissionsStore();
const ui = useUiStore();
const { t } = useI18n();

const resource = computed(() => findResource(route.params.resource));
const columns = computed(() => gridColumns(resource.value));

const records = ref([]);
const count = ref(0);
const offset = ref(0);
const ordering = ref("");
const search = ref("");
const filters = ref({});
const failure = ref("");
const loading = ref(true);
const target = ref(null);
const removing = ref(false);

let timer = null;

const answers = newest();

async function load() {
    const attempt = answers.take();
    loading.value = true;
    failure.value = "";

    try {
        const payload = await api.get(`/${resource.value.name}`, { limit: PAGE_SIZE, offset: offset.value, search: search.value, ordering: ordering.value, ...filters.value });

        if (answers.stale(attempt)) {
            return;
        }

        records.value = payload.items;
        count.value = payload.count;
    } catch (error) {
        if (!answers.stale(attempt)) {
            failure.value = error.message;
        }
    } finally {
        if (!answers.stale(attempt)) {
            loading.value = false;
        }
    }
}

function reset() {
    records.value = [];
    count.value = 0;
    offset.value = 0;
    ordering.value = defaultOrdering(resource.value);
    search.value = "";
    filters.value = Object.fromEntries(resource.value.filters.map((filter) => [filter.name, null]));
}

// A filter that moves empties the ones narrowed by it, the same way the form does.
function onFilterChange(name, value) {
    const emptied = Object.fromEntries(dependentsOf(resource.value.filters, name).map((child) => [child, null]));

    filters.value = { ...filters.value, [name]: value, ...emptied };
    offset.value = 0;
    load();
}

function onSort(next) {
    ordering.value = next;
    load();
}

function onPage(next) {
    offset.value = next;
    load();
}

function clearFilters() {
    search.value = "";
    filters.value = Object.fromEntries(Object.keys(filters.value).map((name) => [name, null]));
    offset.value = 0;
    load();
}

async function confirmRemove() {
    removing.value = true;

    try {
        await api.remove(`/${resource.value.name}/${target.value.id}`);

        ui.success(t("message.deleted"));
        target.value = null;

        // The last row of the last page leaves that page empty, so the listing goes back to the one that still has rows.
        if (records.value.length === 1 && offset.value > 0) {
            offset.value = Math.max(0, offset.value - PAGE_SIZE);
        }

        await load();
    } catch (error) {
        ui.error(error.message);
    } finally {
        removing.value = false;
    }
}

watch(search, () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
        offset.value = 0;
        load();
    }, SEARCH_DELAY);
});

onBeforeUnmount(() => clearTimeout(timer));

watch(
    () => route.params.resource,
    () => {
        reset();
        load();
    },
    { immediate: true },
);
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t(`resource.${resource.name}.title`) }}</h1>
        </template>

        <AppCard flush class="overflow-hidden">
            <div class="flex flex-col gap-4 border-b border-line px-5 py-4 lg:flex-row lg:items-end lg:px-6">
                <ResourceFilters class="min-w-0 flex-1" :filters="resource.filters" :values="filters" :search="search" :searchable="resource.searchable !== false" @update:search="search = $event" @change="onFilterChange" @clear="clearFilters" />

                <AppButton v-if="canCreate(resource)" icon="plus" class="self-end" @click="router.push({ name: 'resource-create', params: { resource: resource.name } })">
                    {{ $t("action.create") }}
                </AppButton>
            </div>

            <AppAlert v-if="failure" tone="error" class="mx-5 mt-4 lg:mx-6">{{ failure }}</AppAlert>

            <DataGrid
                :columns="columns"
                :records="records"
                :loading="loading"
                :ordering="ordering"
                :orderable="resource.ordering"
                :empty-message="search ? $t('common.emptySearch') : $t('common.empty')"
                :can-view="canView(resource)"
                :can-edit="canEdit(resource)"
                :can-delete="canDelete(resource)"
                :writable="(record) => permissions.writes(resource, record)"
                :actions="resource.rowActions || []"
                @sort="onSort"
                @view="router.push({ name: 'resource-detail', params: { resource: resource.name, id: $event.id } })"
                @edit="router.push({ name: 'resource-edit', params: { resource: resource.name, id: $event.id } })"
                @remove="target = $event"
            />

            <AppPagination v-if="count > 0" :count="count" :limit="PAGE_SIZE" :offset="offset" @change="onPage" />
        </AppCard>

        <DeleteConfirm :open="Boolean(target)" :named="target ? labelOf(resource, target) : ''" :working="removing" @confirm="confirmRemove" @close="target = null" />
    </AppShell>
</template>
