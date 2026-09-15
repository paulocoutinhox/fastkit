<script setup>
// The editor is self hosted, so the core loads before anything that registers itself on it.
import "tinymce/tinymce";
import "tinymce/models/dom";
import "tinymce/themes/silver";
import "tinymce/icons/default";

import darkContent from "tinymce/skins/content/dark/content.css?raw";
import lightContent from "tinymce/skins/content/default/content.css?raw";
import darkSkin from "tinymce/skins/ui/oxide-dark/skin.css?raw";
import lightSkin from "tinymce/skins/ui/oxide/skin.css?raw";

import "tinymce/plugins/advlist";
import "tinymce/plugins/anchor";
import "tinymce/plugins/autolink";
import "tinymce/plugins/charmap";
import "tinymce/plugins/code";
import "tinymce/plugins/codesample";
import "tinymce/plugins/fullscreen";
import "tinymce/plugins/image";
import "tinymce/plugins/insertdatetime";
import "tinymce/plugins/link";
import "tinymce/plugins/lists";
import "tinymce/plugins/media";
import "tinymce/plugins/preview";
import "tinymce/plugins/searchreplace";
import "tinymce/plugins/table";
import "tinymce/plugins/visualblocks";
import "tinymce/plugins/wordcount";
import "tinymce-i18n/langs/es";
import "tinymce-i18n/langs/pt_BR";

import { computed, watch } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import { useMetaStore } from "@/stores/meta";
import { useThemeStore } from "@/stores/theme";
import Editor from "@tinymce/tinymce-vue";

const PLUGINS = "autolink code image link lists";
const TOOLBAR = "undo redo | bold italic | bullist numlist | link image | blocks removeformat code";

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: String, default: "" },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { locale } = useI18n();
const meta = useMetaStore();
const theme = useThemeStore();

async function uploadImage(blobInfo) {
    const payload = await api.upload("image", new File([blobInfo.blob()], blobInfo.filename()));

    return `${meta.storageBaseUrl}/${payload.key}`;
}

// The skin and the content CSS are bundled, so the editor never reaches for a cdn.
// Both palettes are carried, because the skin is a stylesheet of its own and a light editor inside a dark panel is the one screen the theme never reached.
const SKIN = document.createElement("style");

SKIN.dataset.tinymceSkin = "";
document.head.appendChild(SKIN);

// What the editor calls each language this panel offers, because its catalogue names them differently and english is the one it already carries.
const EDITOR_LANGUAGES = { en: "en", pt: "pt_BR", es: "es" };

const dark = computed(() => theme.chosen === "dark" || (theme.chosen === "system" && matchMedia("(prefers-color-scheme: dark)").matches));

watch(dark, (wanted) => (SKIN.textContent = wanted ? darkSkin : lightSkin), { immediate: true });

const configuration = computed(() => ({
    height: 360,
    menubar: false,
    statusbar: false,
    plugins: PLUGINS,
    toolbar: TOOLBAR,
    toolbar_mode: "sliding",
    language: EDITOR_LANGUAGES[locale.value],
    skin: false,
    content_css: false,
    content_style: dark.value ? darkContent : lightContent,
    branding: false,
    promotion: false,
    relative_urls: false,
    remove_script_host: false,
    convert_urls: true,
    images_upload_handler: uploadImage,
    automatic_uploads: true,
    file_picker_types: "image",
}));

function onUpdate(value) {
    emit("update:modelValue", value || null);
}
</script>

<template>
    <div class="editor-shell" :class="{ 'editor-shell-invalid': error }">
        <!-- the wrapper overwrites init.license_key with this prop, so the gpl build is declared here -->
        <!-- the editor reads its init once, so turning the palette builds it again instead of leaving it in the one it opened with -->
        <Editor :id="inputId" :key="dark ? 'dark' : 'light'" license-key="gpl" :model-value="modelValue ?? ''" :init="configuration" :disabled="field.readOnly" @update:model-value="onUpdate" />
    </div>
</template>
