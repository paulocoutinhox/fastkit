<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import { configure } from "@/api/client";
import { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES } from "@/i18n";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { useUiStore } from "@/stores/ui";

const { locale, t } = useI18n();
const auth = useAuthStore();
const ui = useUiStore();
const theme = useThemeStore();
const router = useRouter();

const named = computed(() => auth.user?.displayName || auth.user?.username || "");

// A picture is what an account chose to be known by, and what it has instead is the name it is known by.
const initials = computed(
    () =>
        (named.value || "?")
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((word) => word[0])
            .join("")
            .toUpperCase() || "?",
);

function changeLocale(event) {
    locale.value = event.target.value;
    localStorage.setItem(LOCALE_STORAGE_KEY, locale.value);
    configure({ locale: locale.value });
}

function signOut() {
    auth.signOut();
    ui.info(t("message.signedOut"));
    router.push({ name: "login" });
}
</script>

<template>
    <header class="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-raised/90 px-4 py-3 backdrop-blur lg:px-6">
        <button type="button" class="rounded-lg p-2 text-ink-muted transition hover:bg-sunken lg:hidden" :aria-label="$t('common.menu')" @click="ui.toggleSidebar()">
            <AppIcon name="menu" :size="20" />
        </button>

        <div class="min-w-0 flex-1">
            <slot />
        </div>

        <select :value="locale" class="rounded-lg border border-line-strong bg-raised px-2 py-1.5 text-xs text-ink-muted" :aria-label="$t('common.language')" @change="changeLocale">
            <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">{{ code.toUpperCase() }}</option>
        </select>

        <AppButton variant="ghost" size="sm" :icon="theme.chosen === 'dark' ? 'sun' : theme.chosen === 'light' ? 'moon' : 'display'" :title="$t(`theme.${theme.next()}`)" @click="theme.turn()" />

        <div class="hidden items-center gap-2 border-l border-line pl-3 sm:flex">
            <img v-if="auth.user?.avatarUrl" :src="auth.user.avatarUrl" :alt="named" class="size-8 shrink-0 rounded-full object-cover ring-1 ring-line" />
            <span v-else class="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-ink">{{ initials }}</span>

            <span class="max-w-32 truncate text-sm text-ink-muted">{{ named }}</span>
        </div>

        <AppButton variant="ghost" size="sm" icon="logout" :title="$t('action.signOut')" @click="signOut" />
    </header>
</template>
