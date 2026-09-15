<script setup>
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import { api } from "@/api/client";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: null },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { t } = useI18n();
const meta = useMetaStore();
const ui = useUiStore();

const uploading = ref(false);

const fileName = computed(() => (props.modelValue ? props.modelValue.split("/").pop() : ""));
const fileUrl = computed(() => (props.modelValue ? `${meta.storageBaseUrl}/${props.modelValue}` : ""));

// A field may take its extension from a sibling, so the picker only offers what the record will accept.
const accept = computed(() => props.field.accept);

async function onPick(event) {
    const file = event.target.files?.[0];

    if (!file) {
        return;
    }

    uploading.value = true;

    try {
        const payload = await api.upload(props.field.purpose, file);

        emit("update:modelValue", payload.key);
        ui.success(t("message.uploaded"));
    } catch (failure) {
        ui.error(failure.errors?.file || failure.message);
    } finally {
        uploading.value = false;
        event.target.value = "";
    }
}
</script>

<template>
    <div class="space-y-2">
        <div class="flex flex-wrap items-center gap-2">
            <label :for="inputId" class="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-raised px-3.5 py-2 text-sm font-medium text-ink-soft shadow-xs ring-1 ring-line-strong transition hover:bg-sunken">
                <AppIcon name="upload" :size="16" />
                {{ uploading ? $t("common.loading") : $t("action.upload") }}
            </label>

            <input :id="inputId" type="file" class="sr-only" :accept="accept" :disabled="field.readOnly || uploading" @change="onPick" />

            <AppButton v-if="modelValue" variant="ghost" size="sm" icon="trash" class="text-danger" @click="emit('update:modelValue', null)">{{ $t("action.remove") }}</AppButton>
        </div>

        <a v-if="fileName" :href="fileUrl" target="_blank" rel="noreferrer" class="inline-flex items-center gap-1.5 text-xs text-brand-ink hover:underline">
            <AppIcon name="document" :size="14" />
            {{ fileName }}
        </a>
    </div>
</template>
