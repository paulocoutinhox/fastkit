<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api } from "@/api/client";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppLogo from "@/components/ui/AppLogo.vue";
import LocaleSelect from "@/components/ui/LocaleSelect.vue";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { mintSignInToken } from "@/support/captcha";

const auth = useAuthStore();
const meta = useMetaStore();
const route = useRoute();
const router = useRouter();

const login = ref("");
const password = ref("");
const failure = ref("");
const working = ref(false);
const challenge = ref({ provider: "disabled", token: "", image: "", siteKey: "" });
const answer = ref("");

// The challenge is minted for the attempt about to be made, so a refused sign in draws a new one.
// A server that does not answer is said where the person is looking, instead of leaving a form nothing can send.
async function draw() {
    try {
        challenge.value = await api.get("/meta/captcha");
        answer.value = "";
    } catch (error) {
        failure.value = error.message;
    }
}

onMounted(() => Promise.all([draw(), meta.load().catch((error) => (failure.value = error.message))]));

async function solved() {
    if (challenge.value.provider === "recaptcha-v3") {
        return await mintSignInToken(challenge.value.siteKey, document);
    }

    return answer.value;
}

// The address the operator was sent away from, and only when it is a screen of the panel other than this one.
function landing() {
    const next = route.query.next;
    const target = typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? router.resolve(next) : null;

    return target?.matched.length && !target.meta.anonymous ? target.fullPath : { name: "dashboard" };
}

async function submit() {
    failure.value = "";
    working.value = true;

    try {
        await auth.signIn(login.value, password.value, await solved(), challenge.value.token);
        router.push(landing());
    } catch (error) {
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

                <div v-if="challenge.provider === 'image'" class="space-y-1.5">
                    <label for="captcha" class="block text-sm font-medium text-ink-soft">{{ $t("auth.captcha") }}</label>
                    <img :src="challenge.image" :alt="$t('auth.captcha')" width="200" height="64" class="rounded-lg border border-line" />
                    <input id="captcha" v-model="answer" type="text" autocomplete="off" required class="field-control uppercase" />
                </div>

                <AppButton type="submit" class="w-full" size="lg" :loading="working">{{ $t("action.signIn") }}</AppButton>
            </form>
        </div>
    </div>
</template>
