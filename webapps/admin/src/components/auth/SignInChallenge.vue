<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import { mintSignInToken } from "@/support/captcha";

const props = defineProps({ id: { type: String, default: "captcha" } });
const emit = defineEmits(["failure"]);
const { t } = useI18n();
const challenge = ref(null);
const answer = ref("");
const ready = computed(() => challenge.value !== null);

async function reset() {
    challenge.value = await api.get("/meta/captcha");
    answer.value = "";
}

async function solve() {
    if (challenge.value === null) {
        throw new Error(t("auth.challengeNotReady"));
    }

    const captchaAnswer = challenge.value.provider === "recaptcha-v3" ? await mintSignInToken(challenge.value.siteKey, document) : answer.value;

    return { captchaAnswer, captchaToken: challenge.value.token };
}

onMounted(() => reset().catch((error) => emit("failure", error.message)));
defineExpose({ ready, reset, solve });
</script>

<template>
    <div v-if="challenge?.provider === 'image'" class="space-y-1.5">
        <label :for="props.id" class="block text-sm font-medium text-ink-soft">{{ $t("auth.captcha") }}</label>
        <img :src="challenge.image" :alt="$t('auth.captcha')" width="200" height="64" class="rounded-lg border border-line" />
        <input :id="props.id" v-model="answer" type="text" autocomplete="off" required class="field-control uppercase" />
    </div>
</template>
