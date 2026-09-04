<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { api, configure } from "@/api/client";
import AppAlert from "@/components/ui/AppAlert.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppIcon from "@/components/ui/AppIcon.vue";
import { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES } from "@/i18n";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { mintRecaptcha } from "@/support/captcha";

const { locale } = useI18n();
const auth = useAuthStore();
const meta = useMetaStore();
const router = useRouter();

const login = ref("");
const password = ref("");
const failure = ref("");
const working = ref(false);
const challenge = ref({ provider: "disabled", token: "", image: "", siteKey: "" });
const answer = ref("");

// The challenge is minted for the attempt about to be made, so a refused sign in draws a new one.
async function draw() {
    challenge.value = await api.get("/meta/captcha");
    answer.value = "";
}

onMounted(() => Promise.all([draw(), meta.load()]));

async function solved() {
    if (challenge.value.provider === "recaptcha_v3") {
        return await mintRecaptcha(challenge.value.siteKey, document);
    }

    return answer.value;
}

async function submit() {
    failure.value = "";
    working.value = true;

    try {
        await auth.signIn(login.value, password.value, await solved(), challenge.value.token);
        router.push({ name: "dashboard" });
    } catch (error) {
        failure.value = error.message;
        await draw();
    } finally {
        working.value = false;
    }
}

function changeLocale(event) {
    locale.value = event.target.value;
    localStorage.setItem(LOCALE_STORAGE_KEY, locale.value);
    configure({ locale: locale.value });
}
</script>

<template>
    <div class="flex min-h-full items-center justify-center bg-inverse p-4">
        <div class="w-full max-w-md space-y-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="flex size-10 items-center justify-center rounded-xl bg-brand-600 text-white"><AppIcon name="bolt" :size="20" /></span>
                    <p class="text-lg font-semibold text-white">{{ meta.name }}</p>
                </div>

                <select :value="locale" class="rounded-lg border border-line-strong bg-inverse px-2 py-1.5 text-xs text-ink" :aria-label="$t('common.language')" @change="changeLocale">
                    <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">{{ code.toUpperCase() }}</option>
                </select>
            </div>

            <form class="space-y-5 rounded-2xl bg-raised p-6 shadow-xl" @submit.prevent="submit">
                <div>
                    <h1 class="text-lg font-semibold text-ink">{{ $t("auth.title") }}</h1>
                    <p class="mt-1 text-sm text-ink-muted">{{ $t("auth.subtitle") }}</p>
                </div>

                <AppAlert v-if="failure" tone="error">{{ failure }}</AppAlert>

                <div class="space-y-1.5">
                    <label for="login" class="text-sm font-medium text-ink-soft">{{ $t("auth.login") }}</label>
                    <input id="login" v-model="login" type="text" autocomplete="username" required class="field-control" />
                </div>

                <div class="space-y-1.5">
                    <label for="password" class="text-sm font-medium text-ink-soft">{{ $t("auth.password") }}</label>
                    <input id="password" v-model="password" type="password" autocomplete="current-password" required class="field-control" />
                </div>

                <div v-if="challenge.provider === 'image'" class="space-y-1.5">
                    <label for="captcha" class="text-sm font-medium text-ink-soft">{{ $t("auth.captcha") }}</label>
                    <img :src="challenge.image" :alt="$t('auth.captcha')" width="200" height="64" class="rounded-lg border border-line" />
                    <input id="captcha" v-model="answer" type="text" autocomplete="off" required class="field-control uppercase" />
                </div>

                <AppButton type="submit" class="w-full" size="lg" :loading="working">{{ $t("action.signIn") }}</AppButton>
            </form>
        </div>
    </div>
</template>
