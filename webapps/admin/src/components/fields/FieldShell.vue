<script setup>
import AppIcon from "../ui/AppIcon.vue";

defineProps({
    field: { type: Object, required: true },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});
</script>

<template>
    <div class="space-y-1.5">
        <label :for="inputId" class="flex items-center gap-1.5 text-sm font-medium text-ink-soft">
            {{ field.literal ? field.label : $t(field.label) }}
            <span v-if="field.required || field.requiredOnCreate" class="text-danger" aria-hidden="true">*</span>
        </label>

        <slot />

        <p v-if="field.stored" class="flex items-center gap-1 text-xs text-good">
            <AppIcon name="check" :size="14" />
            {{ $t("field.alreadyStored") }}
        </p>

        <p v-if="error" :id="`${inputId}-error`" class="text-xs text-danger">{{ error }}</p>
        <p v-else-if="field.hint" class="text-xs text-ink-muted">{{ field.literal ? field.hint : $t(field.hint) }}</p>
    </div>
</template>
