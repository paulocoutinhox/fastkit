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
    // A form drawn over another one names its controls apart, or a label points at the control of the form behind it.
    scope: { type: String, default: "field" },
});

const emit = defineEmits(["update:modelValue"]);

const component = computed(() => FIELD_COMPONENTS[props.field.type]);
const inputId = computed(() => `${props.scope}-${props.field.name}`);
const wide = computed(() => ["html", "json", "textarea", "image", "file"].includes(props.field.type));

// Only a choice that depends on another field reads the rest of the form, and any other control would carry it as attributes of its markup.
const related = computed(() => (["select", "lookup"].includes(props.field.type) ? { values: props.values, fields: props.fields } : {}));
</script>

<template>
    <FieldShell :field="field" :error="error" :input-id="inputId" :class="wide ? 'sm:col-span-2' : ''">
        <component :is="component" :field="field" :model-value="modelValue" v-bind="related" :error="error" :input-id="inputId" @update:model-value="emit('update:modelValue', $event)" />
    </FieldShell>
</template>
