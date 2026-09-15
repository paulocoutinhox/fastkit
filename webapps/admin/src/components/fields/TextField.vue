<script setup>
import { refused } from "../../support/refusal.js";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: [String, Number], default: "" },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

function onInput(event) {
    emit("update:modelValue", event.target.value === "" ? null : event.target.value);
}
</script>

<template>
    <input :id="inputId" :type="field.inputType || 'text'" :value="modelValue ?? ''" :maxlength="field.max" :placeholder="field.placeholder" :disabled="field.readOnly" class="field-control" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @input="onInput" />
</template>
