<script setup>
import FieldRenderer from "../fields/FieldRenderer.vue";

defineProps({
    group: { type: Object, required: true },
    values: { type: Object, required: true },
    fields: { type: Array, default: () => [] },
    errors: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["change"]);
</script>

<template>
    <fieldset class="rounded-2xl bg-raised shadow-xs ring-1 ring-line">
        <legend class="sr-only">{{ $t(`group.${group.key}`) }}</legend>

        <div class="border-b border-line px-5 py-3">
            <h2 class="text-sm font-semibold text-ink">{{ $t(`group.${group.key}`) }}</h2>
        </div>

        <div class="grid gap-5 p-5 sm:grid-cols-2">
            <FieldRenderer v-for="field in group.fields" :key="field.name" :field="field" :model-value="values[field.name]" :values="values" :fields="fields" :error="errors[field.name]" @update:model-value="emit('change', field.name, $event)" />
        </div>
    </fieldset>
</template>
