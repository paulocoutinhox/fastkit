<script setup>
import { refused } from "../../support/refusal.js";

defineProps({
    field: { type: Object, required: true },
    modelValue: { type: [Number, String], default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

function onInput(event) {
    const raw = event.target.value;

    emit("update:modelValue", raw === "" ? null : Number(raw));
}
</script>

<template>
    <input :id="inputId" type="number" :value="modelValue ?? ''" :min="field.min" :max="field.max" :step="field.step || 1" :disabled="field.readOnly" class="field-control tabular-nums" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @input="onInput" />
</template>
