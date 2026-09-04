<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import FieldRenderer from "../fields/FieldRenderer.vue";
import AppAlert from "../ui/AppAlert.vue";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import AppModal from "../ui/AppModal.vue";
import ValueDisplay from "../ui/ValueDisplay.vue";
import DeleteConfirm from "./DeleteConfirm.vue";
import { api } from "@/api/client";
import { canCreate, canDelete, canEdit, editableFields, findResource } from "@/resources";
import { useUiStore } from "@/stores/ui";
import { defaults, pickValues } from "@/support/values";

// A picture says what it is on its own, so a word in front of it only takes room from the row.
const SHOWN_WITHOUT_A_LABEL = ["thumbnail", "image", "file"];

const props = defineProps({
    subitem: { type: Object, required: true },
    parentId: { type: [String, Number], required: true },
});

const ui = useUiStore();
const { t } = useI18n();

const child = computed(() => findResource(props.subitem.resource));
const columns = computed(() => child.value.columns.filter((column) => column.name !== props.subitem.foreignKey && column.name !== props.subitem.foreignKey.replace(/Id$/, "")));
const fields = computed(() => editableFields(child.value).filter((field) => field.name !== props.subitem.foreignKey));

const records = ref([]);
const total = ref(0);
const values = ref({});
const errors = ref({});
const failure = ref("");
const loading = ref(true);
const saving = ref(false);
const open = ref(false);
const editing = ref(null);
const target = ref(null);
const removing = ref(false);
const moving = ref(false);

// A parent holding more children than one page draws is one this panel cannot show whole.
const partial = computed(() => total.value > records.value.length);

// The panel only offers to reorder what the API knows how to reorder, and never an order it would write for rows nobody could see.
const reorderable = computed(() => Boolean(props.subitem.orderBy) && canEdit(child.value) && !partial.value);

// A child that owns children of its own opens them in place, so the operator never leaves the parent to curate them.
const nested = computed(() => (child.value.subitems || [])[0] || null);
const unfolded = ref([]);

function fold(record) {
    unfolded.value = unfolded.value.includes(record.id) ? unfolded.value.filter((id) => id !== record.id) : [...unfolded.value, record.id];
}

// The parent is not a field here, but a field that hangs off it still has to read it.
function seeded(values) {
    return { ...values, [props.subitem.foreignKey]: Number(props.parentId) };
}

async function load() {
    loading.value = true;

    try {
        const query = { limit: 100, [props.subitem.foreignKey]: props.parentId };

        if (props.subitem.orderBy) {
            query.ordering = props.subitem.orderBy;
        }

        const payload = await api.get(`/${child.value.name}`, query);

        records.value = payload.items;
        total.value = payload.count;
    } catch (error) {
        failure.value = error.message;
    } finally {
        loading.value = false;
    }
}

function start(record) {
    editing.value = record;
    values.value = seeded(record ? pickValues(record, fields.value) : defaults(fields.value));
    errors.value = {};
    failure.value = "";
    open.value = true;
}

function onChange(name, value) {
    values.value = { ...values.value, [name]: value };
    errors.value = { ...errors.value, [name]: undefined };
}

async function save() {
    saving.value = true;
    errors.value = {};
    failure.value = "";

    const payload = { ...values.value, [props.subitem.foreignKey]: props.parentId };

    try {
        if (editing.value) {
            await api.put(`/${child.value.name}/${editing.value.id}`, payload);
        } else {
            await api.post(`/${child.value.name}`, payload);
        }

        ui.success(t(editing.value ? "message.updated" : "message.created"));
        open.value = false;
        await load();
    } catch (error) {
        errors.value = error.errors || {};
        failure.value = Object.keys(error.errors || {}).length ? "" : error.message;
    } finally {
        saving.value = false;
    }
}

async function confirmRemove() {
    removing.value = true;

    try {
        await api.remove(`/${child.value.name}/${target.value.id}`);

        ui.success(t("message.deleted"));
        target.value = null;
        await load();
    } catch (error) {
        ui.error(error.message);
    } finally {
        removing.value = false;
    }
}

async function move(index, step) {
    const ids = records.value.map((record) => record.id);

    ids.splice(index + step, 0, ids.splice(index, 1)[0]);
    moving.value = true;

    try {
        records.value = await api.put(`/${child.value.name}/order`, { ids });
    } catch (error) {
        ui.error(error.message);
        await load();
    } finally {
        moving.value = false;
    }
}

watch(() => props.parentId, load, { immediate: true });
</script>

<template>
    <fieldset class="rounded-2xl bg-raised shadow-xs ring-1 ring-line">
        <legend class="sr-only">{{ $t(`resource.${child.name}.title`) }}</legend>

        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
            <h2 class="text-sm font-semibold text-ink">{{ $t(`resource.${child.name}.title`) }}</h2>

            <AppButton v-if="canCreate(child) && !open" size="sm" icon="plus" @click="start(null)">{{ $t("action.add") }}</AppButton>
        </div>

        <AppModal :open="open" :title="$t(`resource.${child.name}.singular`)" wide @close="open = false">
            <AppAlert v-if="failure" tone="error" class="mb-4">{{ failure }}</AppAlert>

            <div class="grid gap-4 sm:grid-cols-2">
                <FieldRenderer v-for="field in fields" :key="field.name" :field="field" :model-value="values[field.name]" :values="values" :fields="fields" :error="errors[field.name]" @update:model-value="onChange(field.name, $event)" />
            </div>

            <template #actions>
                <AppButton variant="secondary" @click="open = false">{{ $t("action.cancel") }}</AppButton>
                <AppButton icon="check" :loading="saving" @click="save">{{ $t("action.save") }}</AppButton>
            </template>
        </AppModal>

        <AppAlert v-if="partial" tone="warning" class="mx-5 mb-4">{{ $t("message.partialSubitems", { drawn: records.length, total }) }}</AppAlert>

        <p v-if="loading" class="px-5 py-6 text-sm text-ink-muted">{{ $t("common.loading") }}</p>

        <p v-else-if="!records.length" class="px-5 py-6 text-sm text-ink-muted">{{ $t("common.empty") }}</p>

        <ul v-else class="divide-y divide-line">
            <li v-for="(record, index) in records" :key="record.id">
                <div class="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                    <div class="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
                        <button v-if="nested" type="button" class="rounded-lg p-1 text-ink-faint transition hover:bg-sunken hover:text-ink-soft" :title="$t(`resource.${nested.resource}.title`)" @click="fold(record)">
                            <AppIcon :name="unfolded.includes(record.id) ? 'chevronDown' : 'chevronRight'" :size="16" />
                        </button>

                        <span class="font-mono text-xs text-ink-faint">#{{ record.id }}</span>

                        <span v-for="column in columns" :key="column.name" class="flex min-w-0 items-baseline gap-1.5 text-sm">
                            <span v-if="!SHOWN_WITHOUT_A_LABEL.includes(column.type)" class="text-xs text-ink-faint">{{ $t(column.label) }}</span>
                            <ValueDisplay :column="column" :record="record" truncate />
                        </span>
                    </div>

                    <div class="flex shrink-0 items-center gap-1">
                        <button v-if="reorderable" type="button" class="rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-ink-soft disabled:opacity-30" :title="$t('action.moveUp')" :disabled="moving || index === 0" @click="move(index, -1)">
                            <AppIcon name="chevronUp" :size="16" />
                        </button>

                        <button v-if="reorderable" type="button" class="rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-ink-soft disabled:opacity-30" :title="$t('action.moveDown')" :disabled="moving || index === records.length - 1" @click="move(index, 1)">
                            <AppIcon name="chevronDown" :size="16" />
                        </button>

                        <button v-if="canEdit(child)" type="button" class="rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-ink-soft" :title="$t('action.edit')" @click="start(record)">
                            <AppIcon name="pencil" :size="16" />
                        </button>

                        <button v-if="canDelete(child)" type="button" class="rounded-lg p-1.5 text-danger transition hover:bg-danger-soft" :title="$t('action.delete')" @click="target = record">
                            <AppIcon name="trash" :size="16" />
                        </button>
                    </div>
                </div>

                <div v-if="nested && unfolded.includes(record.id)" class="border-t border-line bg-sunken px-5 py-4 pl-12">
                    <SubitemManager :subitem="nested" :parent-id="record.id" />
                </div>
            </li>
        </ul>

        <DeleteConfirm :open="Boolean(target)" :working="removing" @confirm="confirmRemove" @close="target = null" />
    </fieldset>
</template>
