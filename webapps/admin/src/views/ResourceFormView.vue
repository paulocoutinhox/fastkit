<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import FieldGroup from "@/components/resource/FieldGroup.vue";
import SubitemManager from "@/components/resource/SubitemManager.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { canEdit, declaredFields, findResource, subitemsOf } from "@/resources";
import { password } from "@/resources/fields";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import { dependentsOf } from "@/support/dependencies";
import { newest } from "@/support/latest";
import { camelOf } from "@/support/naming";
import { defaults, pickValues } from "@/support/values";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const meta = useMetaStore();
const permissions = usePermissionsStore();
const { t } = useI18n();

const resource = computed(() => findResource(route.params.resource));
const recordId = computed(() => route.params.id || null);
const isEditing = computed(() => Boolean(recordId.value));

const values = ref({});
const record = ref(null);
const errors = ref({});
const failure = ref("");
const loading = ref(true);
const saving = ref("");

// A gateway names its own secrets, so the block of keys is what the chosen one asks for and never a generic set.
function expanded(group) {
    if (!group.fieldsFrom) {
        return group;
    }

    const asked = meta.credentialsOf(values.value[group.fieldsFrom]);

    return { ...group, fields: asked.map((credential) => ({ ...password(camelOf(credential.field), credential.label, { hint: credential.hint, storedBy: `has${camelOf(credential.field).charAt(0).toUpperCase()}${camelOf(credential.field).slice(1)}` }), literal: true })) };
}

// A secret never travels back, so the only way to say one is kept is the flag the record answers.
function told(field) {
    return field.storedBy ? { ...field, stored: Boolean(record.value?.[field.storedBy]) && !values.value[field.name] } : field;
}

// An account that belongs to a brand writes into that brand, so the server settles the field and the form stops offering one option.
const groups = computed(() =>
    (resource.value.groups || [])
        .filter((group) => group.key !== "audit" || isEditing.value)
        .map(expanded)
        .map((group) => ({ ...group, fields: group.fields.filter((field) => field.name !== "tenantId" || !permissions.confined).map(told) }))
        .filter((group) => group.fields.length),
);
const fields = computed(() => groups.value.flatMap((group) => group.fields));

// A subitem hangs off a record that already exists, so it only shows once there is an id to hang it on.
const subitems = computed(() => (isEditing.value ? subitemsOf(resource.value) : []));

// Staying on the form only makes sense where the record may be edited afterwards.
const canKeepEditing = computed(() => canEdit(resource.value));

function defaultValues() {
    return defaults(declaredFields(resource.value));
}

const answers = newest();

function currentValues(record) {
    return pickValues(record, declaredFields(resource.value));
}

async function load() {
    const attempt = answers.take();

    loading.value = true;
    errors.value = {};
    failure.value = "";

    try {
        const found = isEditing.value ? await api.get(`/${resource.value.name}/${recordId.value}`) : null;

        // Moving from one record to the next reuses this screen, and the older answer arriving last would save its values over the record the address names.
        if (answers.stale(attempt)) {
            return;
        }

        record.value = found;
        values.value = found ? currentValues(found) : defaultValues();
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

// A level that moves empties everything hanging below it, so no choice survives the parent it belonged to.
function onChange(name, value) {
    const emptied = Object.fromEntries(dependentsOf(fields.value, name).map((child) => [child, null]));

    values.value = { ...values.value, [name]: value, ...emptied };
    errors.value = { ...errors.value, [name]: undefined };
}

// Leaving a form always lands on the grid, which is where every resource starts.
function goToList() {
    router.push({ name: "resource-list", params: { resource: resource.value.name } });
}

function buildPayload() {
    const payload = {};

    fields.value
        .filter((field) => !field.readOnly)
        .forEach((field) => {
            const value = values.value[field.name];

            if (field.type === "password" && !value) {
                return;
            }

            payload[field.name] = value;
        });

    return payload;
}

async function settle(record, keepEditing) {
    if (!keepEditing) {
        goToList();

        return;
    }

    // A record just created has to become the one being edited, an existing one only refreshes what the API derived.
    if (isEditing.value) {
        await load();

        return;
    }

    router.push({ name: "resource-edit", params: { resource: resource.value.name, id: record.id } });
}

async function submit(action) {
    saving.value = action;
    errors.value = {};
    failure.value = "";

    try {
        const payload = buildPayload();
        const record = await (isEditing.value ? api.put(`/${resource.value.name}/${recordId.value}`, payload) : api.post(`/${resource.value.name}`, payload));

        ui.success(t(isEditing.value ? "message.updated" : "message.created"));
        await settle(record, action === "continue");
    } catch (error) {
        errors.value = error.errors || {};
        failure.value = Object.keys(error.errors || {}).length ? "" : error.message;
    } finally {
        saving.value = "";
    }
}

watch(() => route.fullPath, load, { immediate: true });
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t(`resource.${resource.name}.singular`) }} · {{ isEditing ? $t("action.edit") : $t("action.create") }}</h1>
        </template>

        <div v-if="loading" class="rounded-2xl bg-raised p-12 text-center text-sm text-ink-muted shadow-xs ring-1 ring-line">{{ $t("common.loading") }}</div>

        <form v-else class="space-y-5" @submit.prevent="submit('save')">
            <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

            <FieldGroup v-for="group in groups" :key="group.key" :group="group" :values="values" :fields="fields" :errors="errors" @change="onChange" />

            <SubitemManager v-for="subitem in subitems" :key="subitem.resource" :subitem="subitem" :parent-id="recordId" />

            <div class="sticky bottom-0 z-10 flex flex-col-reverse gap-2 rounded-2xl bg-raised/95 p-4 shadow-lg ring-1 ring-line backdrop-blur sm:flex-row sm:justify-end">
                <AppButton variant="secondary" icon="arrowLeft" @click="goToList">{{ $t("action.cancel") }}</AppButton>
                <AppButton v-if="canKeepEditing" variant="secondary" icon="pencil" :loading="saving === 'continue'" @click="submit('continue')">{{ $t("action.saveAndContinue") }}</AppButton>
                <AppButton type="submit" icon="check" :loading="saving === 'save'">{{ $t("action.save") }}</AppButton>
            </div>
        </form>
    </AppShell>
</template>
