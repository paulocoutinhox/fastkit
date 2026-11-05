<script setup>
import { refused } from "../../support/refusal.js";
import { useMetaStore } from "@/stores/meta";

defineProps({
    field: { type: Object, required: true },
    modelValue: { type: Number, default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const meta = useMetaStore();
</script>

<template>
    <!-- The languages are the ones the boot already read, so this needs no permission over a resource and never offers one the API would refuse.
         What no language means is the column's to say, which is why the empty option is named by the field. -->
    <select :id="inputId" :value="modelValue ?? ''" :disabled="field.readOnly" class="field-control" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @change="emit('update:modelValue', $event.target.value === '' ? null : Number($event.target.value))">
        <option value="">{{ $t(field.empty) }}</option>
        <option v-for="language in meta.languages" :key="language.id" :value="language.id">{{ language.nativeName }}</option>
    </select>
</template>
