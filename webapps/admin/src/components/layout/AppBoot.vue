<script setup>
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
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
    <div class="flex h-full flex-col items-center justify-center gap-5 bg-inverse text-ink-faint">
        <span class="flex size-14 items-center justify-center rounded-2xl bg-brand-600 text-white"><AppIcon name="bolt" :size="26" /></span>

        <div class="flex flex-col items-center gap-3">
            <p class="text-sm font-medium text-white">{{ meta.name || " " }}</p>
            <p class="text-xs text-ink-faint">{{ ui.bootFailure || $t("common.loading") }}</p>
        </div>

        <AppButton v-if="ui.bootFailure" @click="again">{{ $t("common.retry") }}</AppButton>
        <span v-else class="size-5 animate-spin rounded-full border-2 border-line-strong border-t-brand-500" role="status" :aria-label="$t('common.loading')" />
    </div>
</template>
