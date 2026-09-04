<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { refused } from "../../support/refusal.js";
import { useMetaStore } from "@/stores/meta";
import { isWaiting, parentsOf } from "@/support/dependencies";
import { sortByLabel } from "@/support/sorting";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: [String, Number], default: null },
    values: { type: Object, default: () => ({}) },
    fields: { type: Array, default: () => [] },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { t, te, locale } = useI18n();
const meta = useMetaStore();

const waiting = computed(() => isWaiting(props.field, props.values));

// An option is read by its translation, so the order follows the label and not the stored value.
const options = computed(() => {
    const translated = meta.options(props.field.enumName).map((value) => {
        const key = `enum.${props.field.enumName}.${value}`;

        return { value, label: te(key) ? t(key) : value };
    });

    return sortByLabel(translated, locale.value);
});

const parentLabel = computed(() => {
    const parent = props.fields.find((field) => field.name === parentsOf(props.field)[0]);

    return parent ? t(parent.label) : "";
});
</script>

<template>
    <select :id="inputId" :value="modelValue ?? ''" :disabled="field.readOnly || waiting" class="field-control" :class="{ 'field-control-invalid': error }" v-bind="refused(inputId, error)" @change="emit('update:modelValue', $event.target.value === '' ? null : $event.target.value)">
        <option value="">{{ waiting ? $t("common.selectFirst", { field: parentLabel }) : $t("common.select") }}</option>
        <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
</template>
