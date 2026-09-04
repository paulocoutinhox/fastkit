<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import AppButton from "./AppButton.vue";
import AppIcon from "./AppIcon.vue";
import EmptyState from "./EmptyState.vue";
import ValueDisplay from "./ValueDisplay.vue";
import { useUiStore } from "@/stores/ui";

const props = defineProps({
    columns: { type: Array, required: true },
    records: { type: Array, required: true },
    loading: { type: Boolean, default: false },
    ordering: { type: String, default: "" },
    orderable: { type: Array, default: () => [] },
    emptyMessage: { type: String, required: true },
    canView: { type: Boolean, default: true },
    canEdit: { type: Boolean, default: true },
    canDelete: { type: Boolean, default: true },
    actions: { type: Array, default: () => [] },
});

const { t } = useI18n();
const ui = useUiStore();

// An action either leads somewhere or hands something over, and answering empty is what leaves the icon undrawn.
function valueOf(action, record) {
    return (action.href || action.copy)(record);
}

async function copy(action, record) {
    try {
        await navigator.clipboard.writeText(valueOf(action, record));
        ui.success(t("message.copied"));
    } catch {
        ui.error(t("message.copyFailed"));
    }
}

const emit = defineEmits(["sort", "view", "edit", "remove"]);

// The row takes whoever clicks it to the furthest they may go, and stays inert when there is nowhere.
const openable = computed(() => props.canEdit || props.canView);

// A grid header is drawn in caps, and doing it here is what keeps every catalog and every layout agreeing.
function heading(column) {
    return t(column.label).toLocaleUpperCase();
}

function sortable(column) {
    return props.orderable.includes(column.name);
}

function sortState(column) {
    if (props.ordering === column.name) {
        return "asc";
    }

    return props.ordering === `-${column.name}` ? "desc" : "";
}

function toggleSort(column) {
    emit("sort", sortState(column) === "asc" ? `-${column.name}` : column.name);
}

function open(record) {
    if (props.canEdit) {
        emit("edit", record);

        return;
    }

    if (props.canView) {
        emit("view", record);
    }
}
</script>

<template>
    <div>
        <div v-if="loading" class="flex items-center justify-center gap-3 px-6 py-16 text-sm text-ink-muted">
            <span class="size-4 animate-spin rounded-full border-2 border-line-strong border-t-brand-600" />
            {{ $t("common.loading") }}
        </div>

        <EmptyState v-else-if="!records.length" :message="emptyMessage">
            <slot name="empty-action" />
        </EmptyState>

        <template v-else>
            <div class="hidden overflow-x-auto lg:block">
                <table class="w-full text-left text-sm">
                    <thead class="bg-sunken text-xs tracking-wide text-ink-muted uppercase">
                        <tr>
                            <th v-for="column in columns" :key="column.name" scope="col" class="px-4 py-3 font-semibold whitespace-nowrap">
                                <button v-if="sortable(column)" type="button" class="inline-flex items-center gap-1 transition hover:text-ink" :class="sortState(column) ? 'text-ink' : ''" @click="toggleSort(column)">
                                    {{ heading(column) }}
                                    <AppIcon v-if="sortState(column)" name="chevronDown" :size="12" class="text-brand-ink" :class="sortState(column) === 'asc' ? 'rotate-180' : ''" />
                                </button>

                                <span v-else>{{ heading(column) }}</span>
                            </th>
                            <th scope="col" class="px-4 py-3 text-right font-semibold">&nbsp;</th>
                        </tr>
                    </thead>

                    <tbody class="divide-y divide-line">
                        <tr v-for="record in records" :key="record.id" class="transition hover:bg-sunken" :class="openable ? 'cursor-pointer' : ''" @click="open(record)">
                            <td v-for="column in columns" :key="column.name" class="px-4 py-3 align-middle text-ink-soft">
                                <ValueDisplay :column="column" :record="record" truncate />
                            </td>

                            <td class="px-4 py-3 text-right whitespace-nowrap">
                                <div class="inline-flex items-center gap-1" @click.stop>
                                    <template v-for="action in actions" :key="action.icon">
                                        <a v-if="action.href && valueOf(action, record)" :href="valueOf(action, record)" target="_blank" rel="noopener" class="inline-flex rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-brand-ink" :title="$t(action.title)">
                                            <AppIcon :name="action.icon" :size="16" />
                                        </a>

                                        <button v-else-if="action.copy && valueOf(action, record)" type="button" class="inline-flex rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-brand-ink" :title="$t(action.title)" @click="copy(action, record)">
                                            <AppIcon :name="action.icon" :size="16" />
                                        </button>
                                    </template>

                                    <AppButton v-if="canView" variant="ghost" size="sm" icon="eye" :title="$t('action.view')" @click="emit('view', record)" />
                                    <AppButton v-if="canEdit" variant="ghost" size="sm" icon="pencil" :title="$t('action.edit')" @click="emit('edit', record)" />
                                    <AppButton v-if="canDelete" variant="ghost" size="sm" icon="trash" :title="$t('action.delete')" class="text-danger hover:bg-danger-soft" @click="emit('remove', record)" />
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <ul class="divide-y divide-line lg:hidden">
                <li v-for="record in records" :key="record.id" class="px-4 py-4">
                    <component :is="openable ? 'button' : 'div'" type="button" class="w-full space-y-2 text-left" @click="open(record)">
                        <div v-for="column in columns" :key="column.name" class="flex items-start justify-between gap-3">
                            <span class="text-xs font-medium tracking-wide text-ink-muted">{{ heading(column) }}</span>
                            <span class="min-w-0 text-right text-sm text-ink-soft"><ValueDisplay :column="column" :record="record" truncate /></span>
                        </div>
                    </component>

                    <div class="mt-3 flex items-center justify-end gap-1">
                        <template v-for="action in actions" :key="action.icon">
                            <a v-if="action.href && valueOf(action, record)" :href="valueOf(action, record)" target="_blank" rel="noopener" class="inline-flex rounded-lg border border-line p-2 text-ink-muted transition hover:bg-sunken hover:text-brand-ink" :title="$t(action.title)">
                                <AppIcon :name="action.icon" :size="16" />
                            </a>

                            <button v-else-if="action.copy && valueOf(action, record)" type="button" class="inline-flex rounded-lg border border-line p-2 text-ink-muted transition hover:bg-sunken hover:text-brand-ink" :title="$t(action.title)" @click="copy(action, record)">
                                <AppIcon :name="action.icon" :size="16" />
                            </button>
                        </template>

                        <AppButton v-if="canView" variant="secondary" size="sm" icon="eye" @click="emit('view', record)">{{ $t("action.view") }}</AppButton>
                        <AppButton v-if="canEdit" variant="secondary" size="sm" icon="pencil" @click="emit('edit', record)">{{ $t("action.edit") }}</AppButton>
                        <AppButton v-if="canDelete" variant="secondary" size="sm" icon="trash" class="text-danger" @click="emit('remove', record)">{{ $t("action.delete") }}</AppButton>
                    </div>
                </li>
            </ul>
        </template>
    </div>
</template>
