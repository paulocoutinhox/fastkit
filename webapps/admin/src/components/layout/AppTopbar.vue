<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import AccountAvatar from "../ui/AccountAvatar.vue";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import LocaleSelect from "../ui/LocaleSelect.vue";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { useUiStore } from "@/stores/ui";
import { nameOf } from "@/support/naming";

const { t } = useI18n();
const auth = useAuthStore();
const ui = useUiStore();
const theme = useThemeStore();
const router = useRouter();

const named = computed(() => nameOf(auth.user));

function signOut() {
    auth.signOut();
    ui.info(t("message.signedOut"));
    router.push({ name: "login" });
}
</script>

<template>
    <header class="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 lg:px-8">
        <button type="button" class="-ml-1 rounded-lg p-2 text-ink-muted transition hover:bg-sunken hover:text-ink lg:hidden" :aria-label="$t('common.menu')" :aria-expanded="ui.sidebarOpen" @click="ui.toggleSidebar()">
            <AppIcon name="menu" :size="20" />
        </button>

        <div class="min-w-0 flex-1">
            <slot />
        </div>

        <!-- Everything on this side stands the same height as the picture, because a row of controls that each end somewhere else reads as a row that was never lined up. -->
        <LocaleSelect />

        <AppButton variant="ghost" size="sm" :icon="theme.chosen === 'dark' ? 'sun' : theme.chosen === 'light' ? 'moon' : 'display'" :title="$t(`theme.${theme.next()}`)" @click="theme.turn()" />

        <!-- The rule divides the bar and the rounding belongs to what is clicked, so a border on the link itself would be drawn as an arc cut through the picture.
             It stands aside on a phone, where the title of the screen needs the room and the menu is what carries the way to the account. -->
        <div class="hidden min-w-0 items-center border-l border-line pl-3 sm:flex">
            <RouterLink :to="{ name: 'profile' }" class="flex min-w-0 items-center gap-2 rounded-lg px-1 transition hover:bg-sunken" :title="$t('profile.title')">
                <AccountAvatar :user="auth.user" />

                <span class="hidden max-w-32 truncate pr-1 text-sm text-ink-muted sm:inline">{{ named }}</span>
            </RouterLink>
        </div>

        <AppButton variant="ghost" size="sm" icon="logout" :title="$t('action.signOut')" @click="signOut" />
    </header>
</template>
