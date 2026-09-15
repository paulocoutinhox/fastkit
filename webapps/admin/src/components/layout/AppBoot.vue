<script setup>
import AppButton from "../ui/AppButton.vue";
import AppLogo from "../ui/AppLogo.vue";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";

const meta = useMetaStore();
const ui = useUiStore();

// Nothing is loaded when the boot failed, so starting over is the whole page and never a screen of it.
function again() {
    window.location.reload();
}
</script>

<template>
    <div class="flex h-full flex-col items-center justify-center gap-5 bg-surface text-ink-faint">
        <AppLogo size="boot" />

        <div class="flex flex-col items-center gap-3">
            <p class="text-sm font-medium text-ink">{{ meta.name || " " }}</p>
            <p class="text-xs text-ink-faint">{{ ui.bootFailure || $t("common.loading") }}</p>
        </div>

        <AppButton v-if="ui.bootFailure" @click="again">{{ $t("common.retry") }}</AppButton>
        <span v-else class="size-5 animate-spin rounded-full border-2 border-line-strong border-t-ink" role="status" :aria-label="$t('common.loading')" />
    </div>
</template>
