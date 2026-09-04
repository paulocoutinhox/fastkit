<script setup>
import { refused } from "../../support/refusal.js";

defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: "" },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);
</script>

<template>
    <textarea :id="inputId" :value="modelValue ?? ''" rows="4" :disabled="field.readOnly" class="field-control resize-y" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @input="emit('update:modelValue', $event.target.value === '' ? null : $event.target.value)" />
</template>
