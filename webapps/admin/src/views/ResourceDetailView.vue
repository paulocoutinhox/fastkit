<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import DeleteConfirm from "@/components/resource/DeleteConfirm.vue";
import FormSection from "@/components/resource/FormSection.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import ValueDisplay from "@/components/ui/ValueDisplay.vue";
import { canDelete, canEdit, findResource, labelOf } from "@/resources";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import { newest } from "@/support/latest";
import { heldFlagOf } from "@/support/naming";

const FIELD_COLUMN_TYPES = { switch: "boolean", select: "enum", image: "thumbnail", password: "hidden" };
// How each resource a form points at is named, read by index so a relation the API expands and nobody named here is seen instead of drawn by a guess.
const REFERENCE_LABELS = { tenants: "name", users: "displayName", integrations: "label", products: "name", plans: "name", entitlements: "name", galleries: "title", "content-categories": "name", currencies: "name" };

const route = useRoute();
const router = useRouter();
const permissions = usePermissionsStore();
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
    if (field.type === "lookup" || field.type === "language") {
        // The API answers the expanded relation next to its id, so the detail shows its name instead of a number.
        const relation = field.name.replace(/Id$/, "");
        const expanded = record.value?.[relation];

        if (expanded) {
            return { name: relation, label: field.label, type: "reference", referenceField: field.type === "language" ? "name" : REFERENCE_LABELS[field.resource] };
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

    return meta.credentialsOf(record.value?.[group.fieldsFrom]).map((credential) => ({ name: heldFlagOf(credential.field), label: credential.label, type: "boolean", literal: true }));
}

const sections = computed(() => {
    if (!resource.value) {
        return [];
    }

    // A resource nobody writes declares no form, so what its record says is read from the columns its grid already draws.
    const fromGroups = resource.value.groups ? resource.value.groups.map((group) => ({ key: group.key, columns: columnsOf(group).filter((column) => column.type !== "hidden") })) : [{ key: "summary", columns: resource.value.columns }];
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
        const payload = await api.post(`/${resource.value.name}/${route.params.id}/activate`);

        ui.success(t("message.activated", { count: payload.granted }));
        await load();
    } catch (error) {
        ui.error(error.message);
    } finally {
        activating.value = false;
    }
}

const title = computed(() => (record.value ? labelOf(resource.value, record.value) : ""));

watch(() => route.fullPath, load, { immediate: true });
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t(`resource.${resource.name}.singular`) }} · {{ title }}</h1>
        </template>

        <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

        <AppCard v-else-if="loading"
            ><p class="py-8 text-center text-sm text-ink-muted">{{ $t("common.loading") }}</p></AppCard
        >

        <template v-else-if="record">
            <AppCard flush>
                <div class="divide-y divide-line">
                    <FormSection v-for="section in sections" :key="section.key" :title="$t(`group.${section.key}`)">
                        <dl class="grid gap-x-6 gap-y-5 sm:grid-cols-2">
                            <div v-for="column in section.columns" :key="column.name" :class="['json', 'html'].includes(column.type) ? 'sm:col-span-2' : ''">
                                <dt class="text-sm font-medium text-ink-muted">{{ column.literal ? column.label : $t(column.label) }}</dt>
                                <dd class="mt-1 text-sm break-words text-ink"><ValueDisplay :column="column" :record="record" /></dd>
                            </div>
                        </dl>
                    </FormSection>
                </div>
            </AppCard>

            <DeleteConfirm :open="confirming" :named="title" :working="removing" @confirm="remove" @close="confirming = false" />
        </template>

        <template v-if="record && !loading" #actions>
            <AppButton variant="secondary" icon="arrowLeft" @click="router.push({ name: 'resource-list', params: { resource: resource.name } })"
                ><span class="sr-only sm:not-sr-only">{{ $t("action.back") }}</span></AppButton
            >

            <div class="flex gap-2">
                <AppButton v-if="canDelete(resource) && permissions.writes(resource, record)" variant="danger" icon="trash" @click="confirming = true"
                    ><span class="sr-only sm:not-sr-only">{{ $t("action.delete") }}</span></AppButton
                >
                <AppButton v-if="resource.activatable && permissions.writes(resource, record)" variant="secondary" icon="bolt" :loading="activating" @click="activate"
                    ><span class="sr-only sm:not-sr-only">{{ $t("action.activate") }}</span></AppButton
                >
                <AppButton v-if="canEdit(resource) && permissions.writes(resource, record)" icon="pencil" @click="router.push({ name: 'resource-edit', params: { resource: resource.name, id: record.id } })">{{ $t("action.edit") }}</AppButton>
            </div>
        </template>
    </AppShell>
</template>
