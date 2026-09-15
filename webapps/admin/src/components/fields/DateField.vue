<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import DatePicker from "./DatePicker.vue";
import { formatDate, toInputDate, todayIn } from "@/support/datetime";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { locale } = useI18n();

const localValue = computed(() => toInputDate(props.modelValue));
const display = computed(() => formatDate(props.modelValue, locale.value));
</script>

<template>
    <DatePicker :model-value="localValue" mode="date" :disabled="field.readOnly" :invalid="Boolean(error)" :input-id="inputId" :display="display" :today="todayIn(null)" @update:model-value="emit('update:modelValue', $event || null)" />
</template>
