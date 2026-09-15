<script setup>
import { computed } from "vue";

import LookupField from "../fields/LookupField.vue";
import SelectField from "../fields/SelectField.vue";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";

const props = defineProps({
    filters: { type: Array, default: () => [] },
    values: { type: Object, required: true },
    search: { type: String, default: "" },
    searchable: { type: Boolean, default: true },
});

const emit = defineEmits(["update:search", "change", "clear"]);

// The tenant is the widest cut a grid takes, so it stands right after the search and before what narrows inside it.
const ordered = computed(() => [...props.filters].sort((left, right) => Number(right.name === "tenantId") - Number(left.name === "tenantId")));

const hasActiveFilters = computed(() => props.search !== "" || Object.values(props.values).some((value) => value !== null && value !== ""));
</script>

<template>
    <div class="space-y-3 border-b border-line px-5 py-4">
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <div v-if="searchable" class="sm:col-span-2">
                <label class="mb-1.5 block text-xs font-medium text-ink-muted" for="filter-search">{{ $t("action.search") }}</label>

                <div class="relative">
                    <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-ink-faint"><AppIcon name="search" :size="16" /></span>
                    <input id="filter-search" :value="search" type="search" class="field-control pl-9" :placeholder="$t('common.typeToSearch')" @input="emit('update:search', $event.target.value)" />
                </div>
            </div>

            <div v-for="filter in ordered" :key="filter.name">
                <label class="mb-1.5 block text-xs font-medium text-ink-muted" :for="`field-${filter.name}`">{{ $t(filter.label) }}</label>

                <SelectField v-if="filter.type === 'enum'" :field="filter" :model-value="values[filter.name]" :values="values" :fields="filters" :input-id="`field-${filter.name}`" @update:model-value="emit('change', filter.name, $event)" />

                <LookupField v-else-if="filter.type === 'lookup'" :field="filter" :model-value="values[filter.name]" :values="values" :fields="filters" :input-id="`field-${filter.name}`" @update:model-value="emit('change', filter.name, $event)" />

                <input v-else-if="filter.type === 'text'" :id="`field-${filter.name}`" :value="values[filter.name] ?? ''" type="text" class="field-control" @change="emit('change', filter.name, $event.target.value === '' ? null : $event.target.value)" />

                <select v-else :id="`field-${filter.name}`" :value="values[filter.name] ?? ''" class="field-control" @change="emit('change', filter.name, $event.target.value === '' ? null : $event.target.value)">
                    <option value="">{{ $t("common.all") }}</option>
                    <option value="true">{{ $t("common.yes") }}</option>
                    <option value="false">{{ $t("common.no") }}</option>
                </select>
            </div>
        </div>

        <div v-if="hasActiveFilters" class="flex justify-end">
            <AppButton variant="ghost" size="sm" icon="close" @click="emit('clear')">{{ $t("action.clear") }}</AppButton>
        </div>
    </div>
</template>
