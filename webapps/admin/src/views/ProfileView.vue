<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import SocialConnections from "@/components/auth/SocialConnections.vue";
import AppShell from "@/components/layout/AppShell.vue";
import FieldGroup from "@/components/resource/FieldGroup.vue";
import FormSection from "@/components/resource/FormSection.vue";
import AccountAvatar from "@/components/ui/AccountAvatar.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import { choice, language, password, text, timezone } from "@/resources/fields";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";
import { nameOf } from "@/support/naming";
import { pointAt, unpointed } from "@/support/refusal";
import { pickValues } from "@/support/values";

// This screen writes the account of whoever is signed in, through the addresses that account already answers for itself.
// That is why it asks for no permission over the administrative resource: an editor edits itself here without reaching users at all.
const GROUPS = [
    { key: "identification", fields: [text("firstName", "field.firstName"), text("lastName", "field.lastName"), text("nickname", "field.nickname"), text("username", "field.username")] },
    { key: "contact", fields: [text("email", "field.email", { inputType: "email" }), text("document", "field.document"), text("mobilePhone", "field.mobilePhone")] },
    { key: "profile", fields: [choice("gender", "field.gender", "user_gender"), language("languageId", "field.messagesLanguage", "common.languageOfThePage"), timezone("timezone", "common.timezone")] },
];

// The current one is asked for because holding the session is not the same as knowing the password, and whoever walked up to an open screen holds only the first.
const SECRETS = { key: "password", fields: [password("currentPassword", "field.currentPassword"), password("newPassword", "field.newPassword")] };

const FIELDS = GROUPS.flatMap((group) => group.fields);

const { t } = useI18n();
const auth = useAuthStore();
const meta = useMetaStore();
const ui = useUiStore();

const values = ref({});
const secrets = ref({});
const errors = ref({});
const refusals = ref({});
const failure = ref("");
const loading = ref(true);
const saving = ref(false);
const details = ref(null);
const secretsForm = ref(null);
const changing = ref(false);
const picturing = ref(false);

const named = computed(() => nameOf(auth.user));
const writing = computed(() => saving.value || changing.value || picturing.value);

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
        const account = await auth.refresh();

        if (account === null) {
            return;
        }

        values.value = pickValues(account, FIELDS);
    } catch (error) {
        failure.value = error.message;
    } finally {
        loading.value = false;
    }
}

async function save() {
    const requestedRevision = auth.sessionRevision;
    saving.value = true;
    errors.value = {};
    failure.value = "";

    try {
        const account = await api.put("/account/me", values.value);

        if (auth.remember(account, requestedRevision) === null) {
            return;
        }

        ui.success(t("message.updated"));
    } catch (error) {
        if (auth.sessionRevision !== requestedRevision) {
            return;
        }

        errors.value = error.errors || {};
        failure.value = unpointed(error, FIELDS);
        await pointAt(details.value);
    } finally {
        saving.value = false;
    }
}

// The picture is one call that stores the image and answers the account already carrying it, so nothing on this side ever holds a storage key.
async function settlePicture(sending) {
    const requestedRevision = auth.sessionRevision;
    picturing.value = true;

    try {
        const account = await sending();

        if (auth.remember(account, requestedRevision) === null) {
            return;
        }

        ui.success(t("message.updated"));
    } catch (error) {
        if (auth.sessionRevision !== requestedRevision) {
            return;
        }

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
    const requestedRevision = auth.sessionRevision;
    changing.value = true;
    refusals.value = {};

    try {
        const settled = await api.post("/account/password", secrets.value);

        // A new password ends every session the old one opened, and this one stays in with the token the route answered.
        if (auth.settle(settled.token, settled.user, requestedRevision) === null) {
            return;
        }

        secrets.value = {};
        ui.success(t("message.passwordChanged"));
    } catch (error) {
        if (auth.sessionRevision !== requestedRevision) {
            return;
        }

        refusals.value = error.errors || {};
        await pointAt(secretsForm.value);

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

        <AppCard v-if="loading"
            ><p class="py-8 text-center text-sm text-ink-muted">{{ $t("common.loading") }}</p></AppCard
        >

        <template v-else>
            <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

            <AppAlert v-if="auth.user?.pendingEmail" tone="info">{{ $t("message.addressWaiting", { address: auth.user.pendingEmail }) }}</AppAlert>

            <AppCard flush>
                <div class="divide-y divide-line">
                    <FormSection :title="$t('group.picture')">
                        <div class="flex flex-wrap items-center gap-5">
                            <AccountAvatar :user="auth.user" size="profile" />

                            <div class="min-w-0 flex-1">
                                <p class="truncate text-sm font-medium text-ink">{{ named }}</p>
                                <p v-if="auth.user?.email" class="truncate text-sm text-ink-muted">{{ auth.user.email }}</p>
                            </div>

                            <div class="flex flex-wrap items-center gap-2">
                                <!-- The input takes the focus and the label draws it, so the label is the peer that shows where the keyboard is. -->
                                <input id="account-picture" type="file" accept="image/*" class="peer sr-only" :disabled="writing" @change="pickPicture" />
                                <AppButton as="label" class="peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink-muted" for="account-picture" variant="secondary" icon="upload" :disabled="writing" :loading="picturing">{{ $t("action.upload") }}</AppButton>

                                <AppButton v-if="auth.user?.avatarUrl" variant="ghost" icon="trash" class="text-danger" :disabled="writing" @click="settlePicture(() => api.remove('/account/avatar'))">{{ $t("action.remove") }}</AppButton>
                            </div>
                        </div>
                    </FormSection>

                    <form ref="details" @submit.prevent="save">
                        <div class="divide-y divide-line">
                            <FieldGroup v-for="group in GROUPS" :key="group.key" :group="group" :values="values" :fields="FIELDS" :errors="errors" @change="onChange" />
                        </div>

                        <div class="flex justify-end border-t border-line px-5 py-4 lg:px-6">
                            <AppButton type="submit" icon="check" :disabled="writing && !saving" :loading="saving">{{ $t("action.save") }}</AppButton>
                        </div>
                    </form>
                </div>
            </AppCard>

            <AppCard v-if="auth.user?.hasPassword" flush>
                <form ref="secretsForm" @submit.prevent="changePassword">
                    <FieldGroup :group="SECRETS" :values="secrets" :fields="SECRETS.fields" :errors="refusals" @change="onSecretChange" />

                    <div class="flex justify-end border-t border-line px-5 py-4 lg:px-6">
                        <AppButton type="submit" icon="key" :disabled="writing && !changing" :loading="changing">{{ $t("action.changePassword") }}</AppButton>
                    </div>
                </form>
            </AppCard>

            <AppCard v-else>
                <p class="text-sm text-ink-muted">{{ $t("auth.passwordlessAccount") }}</p>
            </AppCard>

            <SocialConnections :disabled="writing" />
        </template>
    </AppShell>
</template>
