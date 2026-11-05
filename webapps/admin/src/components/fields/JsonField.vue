<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { refused } from "../../support/refusal.js";
import AppButton from "../ui/AppButton.vue";
import { useHold } from "@/support/holds";

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
const hold = useHold();

// A draft that is not JSON is refused here before the server ever sees it, so it names its own message and not the one the form draws below.
const told = computed(() => (parseError.value ? { "aria-invalid": "true", "aria-describedby": `${props.inputId}-draft-error` } : refused(props.inputId, props.error)));

// A draft that is not JSON never reaches the model, so the form waits instead of saving the value from before it.
watch(parseError, (refusal) => hold(Boolean(refusal)));

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
        <div class="flex items-center justify-between gap-2 border-b border-line bg-sunken px-3 py-1">
            <span class="font-mono text-xs text-ink-faint">JSON</span>
            <AppButton variant="ghost" size="sm" @click="format">{{ $t("action.format") }}</AppButton>
        </div>

        <!-- The block class removes the baseline gap an inline textarea leaves under itself, which showed through the rounded corners. -->
        <textarea :id="inputId" v-model="draft" rows="8" spellcheck="false" :disabled="field.readOnly" class="block w-full resize-y bg-raised px-3 py-2 font-mono text-xs text-ink outline-none" v-bind="told" @blur="commit" />
    </div>

    <p v-if="parseError" :id="`${inputId}-draft-error`" class="text-xs text-danger">{{ parseError }}</p>
</template>
