<script setup>
import { computed } from "vue";

import FieldShell from "./FieldShell.vue";
import { FIELD_COMPONENTS } from "./registry";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: null, default: null },
    values: { type: Object, default: () => ({}) },
    fields: { type: Array, default: () => [] },
    error: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const component = computed(() => FIELD_COMPONENTS[props.field.type]);
const inputId = computed(() => `field-${props.field.name}`);
const wide = computed(() => ["html", "json", "textarea", "image", "file"].includes(props.field.type));
</script>

<template>
    <FieldShell :field="field" :error="error" :input-id="inputId" :class="wide ? 'sm:col-span-2' : ''">
        <component :is="component" :field="field" :model-value="modelValue" :values="values" :fields="fields" :error="error" :input-id="inputId" @update:model-value="emit('update:modelValue', $event)" />
    </FieldShell>
</template>
