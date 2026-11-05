<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import EmailCodeLogin from "@/components/auth/EmailCodeLogin.vue";
import SignInChallenge from "@/components/auth/SignInChallenge.vue";
import SocialSignInButtons from "@/components/auth/SocialSignInButtons.vue";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppLogo from "@/components/ui/AppLogo.vue";
import LocaleSelect from "@/components/ui/LocaleSelect.vue";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { AuthenticationHelper } from "@/support/authentication-helper";

const auth = useAuthStore();
const meta = useMetaStore();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const login = ref("");
const password = ref("");
const failure = ref("");
const working = ref(false);
const captcha = ref(null);

// The challenge is minted for the attempt about to be made, so a refused sign in draws a new one.
// A server that does not answer is said where the person is looking, instead of leaving a form nothing can send.
async function draw() {
    try {
        await captcha.value.reset();
    } catch (error) {
        failure.value = error.message;
    }
}

onMounted(() => Promise.all([meta.load().catch((error) => (failure.value = error.message)), finishSocial()]));

async function finishSocial() {
    const parameters = new URLSearchParams(route.hash.slice(1));
    const ticket = parameters.get("sign-in");
    const refused = parameters.get("sign-in-error");

    if (ticket === null && refused === null) {
        return;
    }

    const requestedRevision = auth.sessionRevision;
    working.value = true;

    try {
        await router.replace({ path: route.path, query: route.query, hash: "" });

        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        if (refused !== null) {
            failure.value = t(AuthenticationHelper.socialError(refused));

            return;
        }

        const account = await auth.redeemTicket(ticket);

        if (account !== null) {
            router.push(landing());
        }
    } catch (error) {
        failure.value = error.message;
    } finally {
        working.value = false;
    }
}

// The address the operator was sent away from, and only when it is a screen of the panel other than this one.
function landing() {
    const next = route.query.next;
    const target = typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? router.resolve(next) : null;

    return target?.matched.length && !target.meta.anonymous ? target.fullPath : { name: "dashboard" };
}

async function submit() {
    const requestedRevision = auth.sessionRevision;
    failure.value = "";
    working.value = true;

    try {
        const proof = await captcha.value.solve();

        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        const account = await auth.signIn(login.value, password.value, proof.captchaAnswer, proof.captchaToken);

        if (account === null) {
            return;
        }

        router.push(landing());
    } catch (error) {
        if (requestedRevision !== auth.sessionRevision) {
            return;
        }

        failure.value = error.message;
        await draw();
    } finally {
        working.value = false;
    }
}
</script>

<template>
    <div class="flex min-h-full items-center justify-center bg-surface p-4">
        <div class="w-full max-w-md space-y-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <AppLogo size="entry" />
                    <p class="text-lg font-semibold text-ink">{{ meta.name }}</p>
                </div>

                <LocaleSelect />
            </div>

            <form class="space-y-5 rounded-xl border border-line bg-raised p-6 shadow-sm" @submit.prevent="submit">
                <div>
                    <h1 class="text-lg font-semibold text-ink">{{ $t("auth.title") }}</h1>
                    <p class="mt-1 text-sm text-ink-muted">{{ $t("auth.subtitle") }}</p>
                </div>

                <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

                <div class="space-y-1.5">
                    <label for="login" class="block text-sm font-medium text-ink-soft">{{ $t("auth.login") }}</label>
                    <input id="login" v-model="login" type="text" autocomplete="username" required class="field-control" />
                </div>

                <div class="space-y-1.5">
                    <label for="password" class="block text-sm font-medium text-ink-soft">{{ $t("auth.password") }}</label>
                    <input id="password" v-model="password" type="password" autocomplete="current-password" required class="field-control" />
                </div>

                <SignInChallenge ref="captcha" @failure="failure = $event" />

                <AppButton type="submit" class="w-full" size="lg" :loading="working" :disabled="!captcha?.ready">{{ $t("action.signIn") }}</AppButton>
            </form>

            <EmailCodeLogin v-if="meta.authentication.emailCode" @signed-in="router.push(landing())" />
            <SocialSignInButtons :next="typeof route.query.next === 'string' ? route.query.next : '/'" :disabled="working" />
        </div>
    </div>
</template>
