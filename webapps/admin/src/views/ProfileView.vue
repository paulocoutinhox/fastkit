<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import FieldGroup from "@/components/resource/FieldGroup.vue";
import AccountAvatar from "@/components/ui/AccountAvatar.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppIcon from "@/components/ui/AppIcon.vue";
import { choice, password, text, timezone } from "@/resources/fields";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { nameOf } from "@/support/naming";
import { pickValues } from "@/support/values";

// This screen writes the account of whoever is signed in, through the addresses that account already answers for itself.
// That is why it asks for no permission over the administrative resource: an editor edits itself here without reaching users at all.
const GROUPS = [
    { key: "identification", fields: [text("firstName", "field.firstName"), text("lastName", "field.lastName"), text("nickname", "field.nickname")] },
    { key: "contact", fields: [text("email", "field.email", { inputType: "email" }), text("mobilePhone", "field.mobilePhone")] },
    { key: "profile", fields: [choice("gender", "field.gender", "user_gender"), timezone("timezone", "common.timezone")] },
];

// The current one is asked for because holding the session is not the same as knowing the password, and whoever walked up to an open screen holds only the first.
const SECRETS = { key: "password", fields: [password("currentPassword", "field.currentPassword"), password("newPassword", "field.newPassword")] };

const FIELDS = GROUPS.flatMap((group) => group.fields);

const { t } = useI18n();
const auth = useAuthStore();
const ui = useUiStore();

const values = ref({});
const secrets = ref({});
const errors = ref({});
const refusals = ref({});
const failure = ref("");
const loading = ref(true);
const saving = ref(false);
const changing = ref(false);
const picturing = ref(false);

const named = computed(() => nameOf(auth.user));

function onChange(name, value) {
    values.value = { ...values.value, [name]: value };
    errors.value = { ...errors.value, [name]: undefined };
}

function onSecretChange(name, value) {
    secrets.value = { ...secrets.value, [name]: value };
    refusals.value = { ...refusals.value, [name]: undefined };
}

async function load() {
    loading.value = true;
    failure.value = "";

    try {
        // What is stored was written at sign in, so the form is filled from what the account answers now.
        values.value = pickValues(await auth.refresh(), FIELDS);
    } catch (error) {
        failure.value = error.message;
    } finally {
        loading.value = false;
    }
}

async function save() {
    saving.value = true;
    errors.value = {};
    failure.value = "";

    try {
        auth.remember(await api.put("/account/me", values.value));
        ui.success(t("message.updated"));
    } catch (error) {
        errors.value = error.errors || {};
        failure.value = Object.keys(error.errors || {}).length ? "" : error.message;
    } finally {
        saving.value = false;
    }
}

// The picture is one call that stores the image and answers the account already carrying it, so nothing on this side ever holds a storage key.
async function settlePicture(sending) {
    picturing.value = true;

    try {
        auth.remember(await sending());
        ui.success(t("message.updated"));
    } catch (error) {
        ui.error(error.errors?.file || error.message);
    } finally {
        picturing.value = false;
    }
}

function pickPicture(event) {
    const chosen = event.target.files?.[0];

    if (!chosen) {
        return;
    }

    const body = new FormData();
    body.append("file", chosen);

    settlePicture(() => api.post("/account/avatar", body)).finally(() => {
        event.target.value = "";
    });
}

async function changePassword() {
    changing.value = true;
    refusals.value = {};

    try {
        const settled = await api.post("/account/password", secrets.value);

        // A new password ends every session the old one opened, and this one stays in with the token the route answered.
        auth.settle(settled.token, settled.user);
        secrets.value = {};
        ui.success(t("message.passwordChanged"));
    } catch (error) {
        refusals.value = error.errors || {};

        if (!Object.keys(error.errors || {}).length) {
            ui.error(error.message);
        }
    } finally {
        changing.value = false;
    }
}

onMounted(load);
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="truncate text-base font-semibold text-ink">{{ $t("profile.title") }}</h1>
        </template>

        <div v-if="loading" class="rounded-2xl bg-raised p-12 text-center text-sm text-ink-muted shadow-xs ring-1 ring-line">{{ $t("common.loading") }}</div>

        <template v-else>
            <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

            <section class="rounded-2xl bg-raised shadow-xs ring-1 ring-line">
                <div class="border-b border-line px-5 py-3">
                    <h2 class="text-sm font-semibold text-ink">{{ $t("group.picture") }}</h2>
                </div>

                <div class="flex flex-wrap items-center gap-5 p-5">
                    <AccountAvatar :user="auth.user" size="profile" />

                    <div class="min-w-0 flex-1">
                        <p class="truncate text-sm font-medium text-ink">{{ named }}</p>
                        <p v-if="auth.user?.email" class="truncate text-sm text-ink-muted">{{ auth.user.email }}</p>
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        <label for="account-picture" class="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-raised px-3.5 py-2 text-sm font-medium text-ink-soft shadow-xs ring-1 ring-line-strong transition hover:bg-sunken">
                            <AppIcon name="upload" :size="16" />
                            {{ picturing ? $t("common.loading") : $t("action.upload") }}
                        </label>

                        <input id="account-picture" type="file" accept="image/*" class="sr-only" :disabled="picturing" @change="pickPicture" />

                        <AppButton v-if="auth.user?.avatarUrl" variant="ghost" size="sm" icon="trash" class="text-danger" @click="settlePicture(() => api.remove('/account/avatar'))">{{ $t("action.remove") }}</AppButton>
                    </div>
                </div>
            </section>

            <form class="space-y-5" @submit.prevent="save">
                <FieldGroup v-for="group in GROUPS" :key="group.key" :group="group" :values="values" :fields="FIELDS" :errors="errors" @change="onChange" />

                <div class="flex justify-end">
                    <AppButton type="submit" icon="check" :loading="saving">{{ $t("action.save") }}</AppButton>
                </div>
            </form>

            <form class="space-y-5" @submit.prevent="changePassword">
                <FieldGroup :group="SECRETS" :values="secrets" :fields="SECRETS.fields" :errors="refusals" @change="onSecretChange" />

                <div class="flex justify-end">
                    <AppButton type="submit" icon="key" :loading="changing">{{ $t("action.changePassword") }}</AppButton>
                </div>
            </form>
        </template>
    </AppShell>
</template>
