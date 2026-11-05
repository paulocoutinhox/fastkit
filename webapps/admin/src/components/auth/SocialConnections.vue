<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import { useAuthStore } from "@/stores/auth";
import { AuthenticationHelper } from "@/support/authentication-helper";

const props = defineProps({ disabled: { type: Boolean, default: false } });
const auth = useAuthStore();
const { t } = useI18n();
const connections = ref([]);
const working = ref(false);
const failure = ref("");
const success = ref("");

async function load() {
    const requestedRevision = auth.sessionRevision;

    try {
        const found = await api.get("/account/social-connections", { surface: "admin" });

        if (requestedRevision === auth.sessionRevision) {
            connections.value = found;
        }
    } catch (error) {
        if (requestedRevision === auth.sessionRevision) {
            failure.value = error.message;
        }
    }
}

async function change(connection) {
    const requestedRevision = auth.sessionRevision;
    working.value = true;
    failure.value = "";
    success.value = "";

    try {
        if (connection.connected) {
            await api.remove(`/account/social-connections/${connection.provider}?surface=admin`);

            if (requestedRevision !== auth.sessionRevision) {
                return;
            }

            success.value = t("auth.socialDisconnected");
            await load();

            return;
        }

        const authorization = await api.post(`/account/social-connections/${connection.provider}/start`, { surface: "admin" });

        if (requestedRevision === auth.sessionRevision) {
            AuthenticationHelper.navigate(authorization.authorizationUrl);
        }
    } catch (error) {
        if (requestedRevision === auth.sessionRevision) {
            failure.value = error.message;
        }
    } finally {
        working.value = false;
    }
}

onMounted(load);
</script>

<template>
    <AppCard v-if="connections.length || failure">
        <h2 class="text-base font-semibold text-ink">{{ $t("auth.connectionsTitle") }}</h2>
        <p class="mt-1 text-sm text-ink-muted">{{ $t("auth.connectionsLead") }}</p>

        <AppAlert v-if="failure" tone="error" class="mt-4">{{ failure }}</AppAlert>
        <AppAlert v-if="success" tone="success" class="mt-4">{{ success }}</AppAlert>

        <ul class="mt-4 divide-y divide-line">
            <li v-for="connection in connections" :key="connection.provider" class="flex items-center justify-between gap-4 py-3">
                <span class="text-sm font-medium text-ink">{{ connection.label }}</span>
                <AppButton variant="secondary" :disabled="props.disabled || working" @click="change(connection)">{{ connection.connected ? $t("auth.disconnect") : $t("auth.connect") }}</AppButton>
            </li>
        </ul>
    </AppCard>
</template>
