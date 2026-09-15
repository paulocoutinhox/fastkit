<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import AccountAvatar from "../ui/AccountAvatar.vue";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import { configure } from "@/api/client";
import { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES } from "@/i18n";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { useUiStore } from "@/stores/ui";
import { nameOf } from "@/support/naming";

const { locale, t } = useI18n();
const auth = useAuthStore();
const ui = useUiStore();
const theme = useThemeStore();
const router = useRouter();

const named = computed(() => nameOf(auth.user));

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

        <!-- Everything on this side stands the same height as the picture, because a row of controls that each end somewhere else reads as a row that was never lined up -->
        <select :value="locale" class="h-8 rounded-lg border border-line-strong bg-raised px-2 text-xs text-ink-muted" :aria-label="$t('common.language')" @change="changeLocale">
            <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">{{ code.toUpperCase() }}</option>
        </select>

        <AppButton variant="ghost" :icon="theme.chosen === 'dark' ? 'sun' : theme.chosen === 'light' ? 'moon' : 'display'" :title="$t(`theme.${theme.next()}`)" @click="theme.turn()" />

        <!-- The rule divides the bar and the rounding belongs to what is clicked, so a border on the link itself would be drawn as an arc cut through the picture.
             It stands aside on a phone, where the title of the screen needs the room and the menu is what carries the way to the account -->
        <div class="hidden min-w-0 items-center border-l border-line pl-3 sm:flex">
            <RouterLink :to="{ name: 'profile' }" class="flex min-w-0 items-center gap-2 rounded-lg px-1 transition hover:bg-sunken" :title="$t('profile.title')">
                <AccountAvatar :user="auth.user" />

                <span class="hidden max-w-32 truncate pr-1 text-sm text-ink-muted sm:inline">{{ named }}</span>
            </RouterLink>
        </div>

        <AppButton variant="ghost" icon="logout" :title="$t('action.signOut')" @click="signOut" />
    </header>
</template>
