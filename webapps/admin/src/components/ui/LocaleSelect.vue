<script setup>
import { useI18n } from "vue-i18n";

import { SUPPORTED_LOCALES, speak } from "@/i18n";

const { locale } = useI18n();

function choose(event) {
    speak(locale, event.target.value);
}
</script>

<template>
    <!-- This turns the text of the panel and nothing else: the language of the messages an account receives is chosen on its profile. -->
    <select :value="locale" class="h-8 rounded-lg border border-line-strong bg-raised pr-8 pl-2.5 text-xs text-ink-muted transition hover:text-ink" :aria-label="$t('common.language')" @change="choose">
        <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">{{ code.toUpperCase() }}</option>
    </select>
</template>
