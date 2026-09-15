<script setup>
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import AppModal from "../ui/AppModal.vue";

defineProps({
    open: { type: Boolean, default: false },
    working: { type: Boolean, default: false },
});

const emit = defineEmits(["confirm", "close"]);
</script>

<template>
    <AppModal :open="open" :title="$t('message.confirmDelete')" @close="emit('close')">
        <div class="flex items-start gap-4 py-1">
            <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-danger-soft text-danger">
                <AppIcon name="trash" :size="20" />
            </span>

            <p class="text-sm leading-relaxed text-ink-muted">{{ $t("message.confirmDeleteHint") }}</p>
        </div>

        <template #actions>
            <AppButton variant="secondary" @click="emit('close')">{{ $t("action.cancel") }}</AppButton>
            <AppButton variant="danger" icon="trash" :loading="working" @click="emit('confirm')">{{ $t("action.delete") }}</AppButton>
        </template>
    </AppModal>
</template>
