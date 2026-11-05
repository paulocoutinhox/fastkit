<script setup>
import FieldRenderer from "../fields/FieldRenderer.vue";
import FormSection from "./FormSection.vue";

defineProps({
    group: { type: Object, required: true },
    values: { type: Object, required: true },
    fields: { type: Array, default: () => [] },
    errors: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["change"]);
</script>

<template>
    <fieldset>
        <legend class="sr-only">{{ $t(`group.${group.key}`) }}</legend>

        <FormSection :title="$t(`group.${group.key}`)">
            <div class="grid gap-x-6 gap-y-5 sm:grid-cols-2">
                <FieldRenderer v-for="field in group.fields" :key="field.name" :field="field" :model-value="values[field.name]" :values="values" :fields="fields" :error="errors[field.name]" @update:model-value="emit('change', field.name, $event)" />
            </div>
        </FormSection>
    </fieldset>
</template>
