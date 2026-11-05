<script setup>
import { ref } from "vue";

import { api } from "@/api/client";
import SignInChallenge from "@/components/auth/SignInChallenge.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import { useAuthStore } from "@/stores/auth";

const emit = defineEmits(["signed-in"]);
const auth = useAuthStore();
const email = ref("");
const code = ref("");
const challenge = ref(null);
const captcha = ref(null);
const working = ref(false);
const failure = ref("");

async function requestCode() {
    const requestedRevision = auth.sessionRevision;
    working.value = true;
    failure.value = "";

    try {
        const proof = await captcha.value.solve();

        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        const requested = await api.post("/auth/email/request", { email: email.value, surface: "admin", ...proof });

        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        challenge.value = requested;
    } catch (error) {
        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        failure.value = error.message;

        try {
            await captcha.value.reset();
        } catch (redrawError) {
            failure.value = redrawError.message;
        }
    } finally {
        working.value = false;
    }
}

async function confirmCode() {
    const requestedRevision = auth.sessionRevision;
    working.value = true;
    failure.value = "";

    try {
        const account = await auth.signInWithCode(challenge.value.challenge, code.value);

        if (account !== null) {
            emit("signed-in");
        }
    } catch (error) {
        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        failure.value = error.message;
    } finally {
        working.value = false;
    }
}

function startAgain() {
    challenge.value = null;
    code.value = "";
    failure.value = "";
}
</script>

<template>
    <section class="rounded-xl border border-line bg-raised p-6 shadow-sm">
        <h2 class="text-base font-semibold text-ink">{{ $t("auth.emailCodeTitle") }}</h2>
        <p class="mt-1 text-sm text-ink-muted">{{ $t("auth.emailCodeLead") }}</p>

        <AppAlert v-if="failure" tone="error" class="mt-4">{{ failure }}</AppAlert>

        <form v-if="challenge === null" class="mt-5 space-y-4" @submit.prevent="requestCode">
            <div class="space-y-1.5">
                <label for="sign-in-email" class="block text-sm font-medium text-ink-soft">{{ $t("field.email") }}</label>
                <input id="sign-in-email" v-model="email" type="email" autocomplete="email" required maxlength="255" class="field-control" />
            </div>

            <SignInChallenge ref="captcha" id="email-captcha" @failure="failure = $event" />
            <AppButton type="submit" class="w-full" :loading="working" :disabled="!captcha?.ready">{{ $t("auth.sendCode") }}</AppButton>
        </form>

        <form v-else class="mt-5 space-y-4" @submit.prevent="confirmCode">
            <p class="text-sm text-ink-muted">{{ $t("auth.codeSent", { email }) }}</p>

            <div class="space-y-1.5">
                <label for="sign-in-code" class="block text-sm font-medium text-ink-soft">{{ $t("auth.code") }}</label>
                <input id="sign-in-code" v-model="code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required class="field-control" />
            </div>

            <AppButton type="submit" class="w-full" :loading="working">{{ $t("action.signIn") }}</AppButton>
            <AppButton variant="ghost" class="w-full" :disabled="working" @click="startAgain">{{ $t("auth.requestAnotherCode") }}</AppButton>
        </form>
    </section>
</template>
