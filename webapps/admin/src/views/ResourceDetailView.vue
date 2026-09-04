<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import DeleteConfirm from "@/components/resource/DeleteConfirm.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import ValueDisplay from "@/components/ui/ValueDisplay.vue";
import { canDelete, canEdit, findResource } from "@/resources";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";
import { newest } from "@/support/latest";
import { camelOf } from "@/support/naming";

const FIELD_COLUMN_TYPES = { switch: "boolean", select: "enum", image: "thumbnail", password: "hidden" };
const REFERENCE_LABELS = { tenants: "name", users: "username", products: "name", plans: "name", entitlements: "name", languages: "name" };

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const meta = useMetaStore();
const { t } = useI18n();

const resource = computed(() => findResource(route.params.resource));

const answers = newest();

const record = ref(null);
const loading = ref(true);
const failure = ref("");
const confirming = ref(false);
const removing = ref(false);
const activating = ref(false);

function toColumn(field) {
    if (field.type === "lookup") {
        // The API answers the expanded relation next to its id, so the detail shows the name and links to it.
        const relation = field.name.replace(/Id$/, "");
        const expanded = record.value?.[relation];

        if (expanded) {
            return { name: relation, label: field.label, type: "reference", resource: field.resource, referenceField: REFERENCE_LABELS[field.resource] || "name" };
        }

        return { name: field.name, label: field.label, type: "number" };
    }

    return { name: field.name, label: field.label, type: FIELD_COLUMN_TYPES[field.type] || field.type, enumName: field.enumName };
}

// A secret never travels back, so a group the gateway names is read as whether each key is kept.
function columnsOf(group) {
    if (!group.fieldsFrom) {
        return group.fields.map(toColumn);
    }

    return meta.credentialsOf(record.value?.[group.fieldsFrom]).map((credential) => ({ name: `has${camelOf(credential.field).charAt(0).toUpperCase()}${camelOf(credential.field).slice(1)}`, label: credential.label, type: "boolean", literal: true }));
}

const sections = computed(() => {
    if (!resource.value) {
        return [];
    }

    const fromGroups = (resource.value.groups || []).map((group) => ({ key: group.key, columns: columnsOf(group).filter((column) => column.type !== "hidden") }));
    const extra = resource.value.viewExtra ? [{ key: "outcome", columns: resource.value.viewExtra }] : [];

    return [...fromGroups, ...extra].filter((section) => section.columns.length);
});

async function load() {
    const attempt = answers.take();

    loading.value = true;
    failure.value = "";

    try {
        const found = await api.get(`/${resource.value.name}/${route.params.id}`);

        if (!answers.stale(attempt)) {
            record.value = found;
        }
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

async function remove() {
    removing.value = true;

    try {
        await api.remove(`/${resource.value.name}/${route.params.id}`);

        ui.success(t("message.deleted"));
        router.push({ name: "resource-list", params: { resource: resource.value.name } });
    } catch (error) {
        ui.error(error.message);
    } finally {
        removing.value = false;
        confirming.value = false;
    }
}

async function activate() {
    activating.value = true;

    try {
        const payload = await api.post(`/subscriptions/${route.params.id}/activate`);

        ui.success(t("message.activated", { count: payload.granted }));
        await load();
    } catch (error) {
        ui.error(error.message);
    } finally {
        activating.value = false;
    }
}

const title = computed(() => (record.value ? String(record.value[resource.value.labelField] ?? `#${record.value.id}`) : ""));

watch(() => route.fullPath, load, { immediate: true });
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t(`resource.${resource.name}.singular`) }} · {{ title }}</h1>
        </template>

        <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

        <div v-else-if="loading" class="rounded-2xl bg-raised p-12 text-center text-sm text-ink-muted shadow-xs ring-1 ring-line">{{ $t("common.loading") }}</div>

        <template v-else-if="record">
            <div class="flex flex-wrap items-center justify-between gap-3">
                <AppButton variant="secondary" icon="arrowLeft" @click="router.push({ name: 'resource-list', params: { resource: resource.name } })">{{ $t("action.back") }}</AppButton>

                <div class="flex flex-wrap gap-2">
                    <AppButton v-if="resource.activatable" variant="secondary" icon="bolt" :loading="activating" @click="activate">{{ $t("action.activate") }}</AppButton>
                    <AppButton v-if="canEdit(resource)" icon="pencil" @click="router.push({ name: 'resource-edit', params: { resource: resource.name, id: record.id } })">{{ $t("action.edit") }}</AppButton>
                    <AppButton v-if="canDelete(resource)" variant="danger" icon="trash" @click="confirming = true">{{ $t("action.delete") }}</AppButton>
                </div>
            </div>

            <AppCard v-for="section in sections" :key="section.key" :title="$t(`group.${section.key}`)">
                <dl class="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                    <div v-for="column in section.columns" :key="column.name" :class="['json', 'html'].includes(column.type) ? 'sm:col-span-2' : ''">
                        <dt class="text-xs font-medium tracking-wide text-ink-muted uppercase">{{ $t(column.label) }}</dt>
                        <dd class="mt-1 text-sm break-words text-ink-soft"><ValueDisplay :column="column" :record="record" /></dd>
                    </div>
                </dl>
            </AppCard>

            <DeleteConfirm :open="confirming" :working="removing" @confirm="remove" @close="confirming = false" />
        </template>
    </AppShell>
</template>
