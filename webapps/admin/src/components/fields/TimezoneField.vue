<script setup>
import { refused } from "../../support/refusal.js";
import { useMetaStore } from "@/stores/meta";

defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const meta = useMetaStore();
</script>

<template>
    <select :id="inputId" :value="modelValue ?? ''" :disabled="field.readOnly" class="field-control" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @change="emit('update:modelValue', $event.target.value === '' ? null : $event.target.value)">
        <option value="">{{ $t("common.select") }}</option>
        <option v-for="zone in meta.timezones" :key="zone" :value="zone">{{ zone }}</option>
    </select>
</template>
