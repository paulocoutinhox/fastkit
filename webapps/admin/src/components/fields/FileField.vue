<script setup>
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { refused } from "../../support/refusal.js";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import { api } from "@/api/client";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";
import { useHold } from "@/support/holds";

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
const hold = useHold();

// A save while the file is on its way up would write the record without it, and the key it answers with would name a file nothing claims.
watch(uploading, hold);

const fileName = computed(() => (props.modelValue ? props.modelValue.split("/").pop() : ""));
const fileUrl = computed(() => (props.modelValue ? `${meta.storageBaseUrl}/${props.modelValue}` : ""));

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
            <!-- The input takes the focus and the label draws it, so the label is the peer that shows where the keyboard is. -->
            <input :id="inputId" type="file" class="peer sr-only" :disabled="field.readOnly || uploading" v-bind="refused(inputId, error)" @change="onPick" />
            <AppButton as="label" class="peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink-muted" :for="inputId" variant="secondary" icon="upload" :loading="uploading">{{ $t("action.upload") }}</AppButton>

            <AppButton v-if="modelValue" variant="ghost" size="sm" icon="trash" class="text-danger" @click="emit('update:modelValue', null)">{{ $t("action.remove") }}</AppButton>
        </div>

        <a v-if="fileName" :href="fileUrl" target="_blank" rel="noreferrer" class="inline-flex items-center gap-1.5 text-xs text-brand-ink hover:underline">
            <AppIcon name="document" :size="14" />
            {{ fileName }}
        </a>
    </div>
</template>
