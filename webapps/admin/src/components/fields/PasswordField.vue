<script setup>
import { ref } from "vue";

import { refused } from "../../support/refusal.js";
import AppIcon from "../ui/AppIcon.vue";

defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: "" },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const visible = ref(false);
</script>

<template>
    <div class="relative">
        <input
            :id="inputId"
            :type="visible ? 'text' : 'password'"
            :value="modelValue ?? ''"
            autocomplete="new-password"
            :disabled="field.readOnly"
            class="field-control pr-10"
            :class="{ 'field-control-invalid': error }"
            v-bind="refused(inputId, error)"
            @input="emit('update:modelValue', $event.target.value === '' ? null : $event.target.value)"
        />

        <button type="button" class="absolute inset-y-0 right-0 flex items-center px-3 text-ink-faint transition hover:text-ink-muted" :aria-label="$t('action.view')" @click="visible = !visible">
            <AppIcon :name="visible ? 'close' : 'eye'" :size="16" />
        </button>
    </div>
</template>
