<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import DatePicker from "./DatePicker.vue";
import { useAuthStore } from "@/stores/auth";
import { formatDateTime, fromInputDateTime, resolveTimezone, toInputDateTime, todayIn } from "@/support/datetime";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { locale } = useI18n();
const auth = useAuthStore();

const timezone = computed(() => resolveTimezone(auth.timezone));
const localValue = computed(() => toInputDateTime(props.modelValue, timezone.value));
const display = computed(() => formatDateTime(props.modelValue, locale.value, timezone.value));
</script>

<template>
    <div class="space-y-1">
        <DatePicker :model-value="localValue" mode="datetime" :disabled="field.readOnly" :invalid="Boolean(error)" :input-id="inputId" :display="display" :today="todayIn(timezone)" @update:model-value="emit('update:modelValue', fromInputDateTime($event, timezone))" />
        <p class="text-xs text-ink-faint">{{ timezone }}</p>
    </div>
</template>
