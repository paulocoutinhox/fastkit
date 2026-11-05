<script>
// The skin and the content CSS are bundled, so the editor never reaches for a cdn.
// There is one skin per page however many editors it holds, and it is the element every editor writes the palette into.
const SKIN = document.createElement("style");

SKIN.dataset.tinymceSkin = "";
document.head.appendChild(SKIN);
</script>

<script setup>
// The editor is self hosted, so the core loads before anything that registers itself on it.
import "tinymce/tinymce";
import "tinymce/models/dom";
import "tinymce/themes/silver";
import "tinymce/icons/default";

import darkContent from "tinymce/skins/content/dark/content.css?raw";
import lightContent from "tinymce/skins/content/default/content.css?raw";

import "tinymce/plugins/autolink";
import "tinymce/plugins/code";
import "tinymce/plugins/image";
import "tinymce/plugins/link";
import "tinymce/plugins/lists";
import "tinymce-i18n/langs/es";
import "tinymce-i18n/langs/pt_BR";

import { computed, shallowRef, watch, watchEffect } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "@/api/client";
import { useMetaStore } from "@/stores/meta";
import { useThemeStore } from "@/stores/theme";
import { useHold } from "@/support/holds";
import { SKINS } from "@/support/skins";
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

const hold = useHold();
let uploading = 0;

// A pasted picture lives as a blob of this tab until its upload answers, and saving before that would store an address nobody else can open.
async function uploadImage(blobInfo) {
    uploading += 1;
    hold(true);

    try {
        const payload = await api.upload("image", new File([blobInfo.blob()], blobInfo.filename()));

        return `${meta.storageBaseUrl}/${payload.key}`;
    } catch (error) {
        // A picture the server refused leaves the text, or its blob would be saved in its place.
        throw { message: error.message, remove: true };
    } finally {
        uploading -= 1;
        hold(uploading > 0);
    }
}

// What the editor calls each language this panel offers, because its catalogue names them differently and english is the one it already carries.
const EDITOR_LANGUAGES = { en: "en", pt: "pt_BR", es: "es" };

// The page inside the editor is a document of its own that cannot read the palette of the panel, so its ground is left clear and the card behind it shows through.
// A frame whose scheme differs from the page around it is painted opaque by the browser, which is why each side names its own.
function contentOf(dark) {
    return `${dark ? darkContent : lightContent}:root { color-scheme: ${dark ? "dark" : "light"}; } body { background-color: transparent; }`;
}

// The palette of the page turns in place, so an editor holding somebody's text and history is never built again for it.
const palette = shallowRef(null);

watchEffect(() => {
    if (palette.value) {
        palette.value.textContent = contentOf(theme.dark);
    }
});

function drawPalette(editor) {
    editor.on("init", () => {
        const sheet = editor.getDoc().createElement("style");

        editor.getDoc().head.appendChild(sheet);
        palette.value = sheet;
    });
}

watch(
    () => theme.dark,
    (wanted) => (SKIN.textContent = wanted ? SKINS.dark : SKINS.light),
    { immediate: true },
);

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
    branding: false,
    promotion: false,
    relative_urls: false,
    remove_script_host: false,
    convert_urls: true,
    images_upload_handler: uploadImage,
    automatic_uploads: true,
    file_picker_types: "image",
    setup: drawPalette,
}));

function onUpdate(value) {
    emit("update:modelValue", value || null);
}
</script>

<template>
    <div class="editor-shell" :class="{ 'editor-shell-invalid': error }">
        <!-- The wrapper overwrites init.license_key with this prop, so the GPL build is declared here. -->
        <!-- The editor reads its init once, so another language builds it again, and it is built inside an element of its own because the editor moves the nodes around it. -->
        <div :key="locale">
            <Editor :id="inputId" license-key="gpl" :model-value="modelValue ?? ''" :init="configuration" :disabled="field.readOnly" @update:model-value="onUpdate" />
        </div>
    </div>
</template>
