<script setup>
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import AppButton from "../ui/AppButton.vue";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: [Object, Array], default: () => ({}) },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { t } = useI18n();

const draft = ref(JSON.stringify(props.modelValue ?? {}, null, 2));
const parseError = ref("");

watch(
    () => props.modelValue,
    (value) => {
        const serialized = JSON.stringify(value ?? {}, null, 2);

        if (serialized !== draft.value.trim()) {
            draft.value = serialized;
        }
    },
);

function commit() {
    if (!draft.value.trim()) {
        parseError.value = "";
        emit("update:modelValue", {});

        return;
    }

    try {
        emit("update:modelValue", JSON.parse(draft.value));
        parseError.value = "";
    } catch {
        parseError.value = t("validation.invalidJson");
    }
}

function format() {
    try {
        draft.value = JSON.stringify(JSON.parse(draft.value || "{}"), null, 2);
        parseError.value = "";
        commit();
    } catch {
        parseError.value = t("validation.invalidJson");
    }
}
</script>

<template>
    <div class="overflow-hidden rounded-lg ring-1" :class="parseError || error ? 'ring-danger' : 'ring-line-strong'">
        <div class="flex items-center justify-between gap-2 border-b border-line-strong bg-inverse px-3 py-1.5">
            <span class="font-mono text-xs text-ink-faint">JSON</span>
            <AppButton variant="ghost" size="sm" class="text-ink-faint hover:bg-ink-soft" @click="format">{{ $t("action.format") }}</AppButton>
        </div>

        <!-- block removes the baseline gap an inline textarea leaves under itself, which showed through the rounded corners -->
        <textarea :id="inputId" v-model="draft" rows="8" spellcheck="false" :disabled="field.readOnly" class="block w-full resize-y bg-inverse px-3 py-2 font-mono text-xs text-ink outline-none" @blur="commit" />
    </div>

    <p v-if="parseError" class="text-xs text-danger">{{ parseError }}</p>
</template>
