import { describe, expect, it, vi } from "vitest";

import { api } from "@/api/client";
import HtmlField from "@/components/fields/HtmlField.vue";
import { useMetaStore } from "@/stores/meta";
import Editor from "@tinymce/tinymce-vue";
import { mount } from "@vue/test-utils";

function mountEditor(modelValue = "", field = {}) {
    return mount(HtmlField, { props: { field: { name: "description", label: "field.description", ...field }, modelValue, inputId: "field-description" } });
}

function configurationOf(wrapper) {
    return wrapper.findComponent(Editor).props("init");
}

describe("HtmlField", () => {
    it("hands the editor the content it is given", () => {
        const wrapper = mountEditor("<p>hello</p>");

        expect(wrapper.findComponent(Editor).props("modelValue")).toBe("<p>hello</p>");
    });

    it("treats a missing value as an empty document", () => {
        expect(mountEditor(null).findComponent(Editor).props("modelValue")).toBe("");
    });

    it("reports what was written and turns an empty document into nothing", async () => {
        const wrapper = mountEditor("");
        const editor = wrapper.findComponent(Editor);

        await editor.vm.$emit("update:modelValue", "<p>written</p>");
        await editor.vm.$emit("update:modelValue", "");

        expect(wrapper.emitted("update:modelValue")).toEqual([["<p>written</p>"], [null]]);
    });

    it("carries its own skin and content style, so it never reaches for a cdn", () => {
        const configuration = configurationOf(mountEditor(""));

        expect(configuration.skin).toBe(false);
        expect(configuration.content_css).toBe(false);
        expect(configuration.content_style).toBeTruthy();
    });

    it("declares the toolbar the editor needs, image included", () => {
        const configuration = configurationOf(mountEditor(""));

        expect(configuration.plugins).toContain("image");
        expect(configuration.plugins).toContain("link");
        expect(configuration.toolbar).toContain("image");
        expect(configuration.automatic_uploads).toBe(true);
    });

    it("keeps the chrome out of the way", () => {
        const configuration = configurationOf(mountEditor(""));

        expect(configuration.menubar).toBe(false);
        expect(configuration.statusbar).toBe(false);
        expect(configuration.toolbar_mode).toBe("sliding");
        expect(
            configuration.toolbar
                .split("|")
                .flatMap((group) => group.trim().split(" "))
                .filter(Boolean).length,
        ).toBeLessThanOrEqual(12);
    });

    it("stores an image through the upload route and answers its url", async () => {
        const meta = useMetaStore();
        meta.storageBaseUrl = "/media";

        const upload = vi.spyOn(api, "upload").mockResolvedValue({ key: "images/content/2026/07/29/one.png" });

        const configuration = configurationOf(mountEditor(""));
        const location = await configuration.images_upload_handler({ blob: () => new Blob(["x"]), filename: () => "one.png" });

        expect(upload.mock.calls[0][0]).toBe("image");
        expect(upload.mock.calls[0][1].name).toBe("one.png");
        expect(location).toBe("/media/images/content/2026/07/29/one.png");
    });

    it("lets an upload the api refused reach the editor", async () => {
        vi.spyOn(api, "upload").mockRejectedValue({ errors: { file: "This file is not a readable image." } });

        const configuration = configurationOf(mountEditor(""));

        await expect(configuration.images_upload_handler({ blob: () => new Blob(["x"]), filename: () => "one.png" })).rejects.toBeTruthy();
    });

    it("follows the language of the admin, and every language it offers has an editor of its own", async () => {
        // Spanish used to fall through to english, so an operator wrote in one language inside a panel speaking another.
        const { i18n } = await import("../setup");
        const { SUPPORTED_LOCALES } = await import("@/i18n");
        const drawn = [];

        for (const locale of SUPPORTED_LOCALES) {
            i18n.global.locale.value = locale;
            drawn.push(configurationOf(mountEditor("")).language);
        }

        expect(drawn.filter(Boolean)).toHaveLength(SUPPORTED_LOCALES.length);
        expect(new Set(drawn).size).toBe(SUPPORTED_LOCALES.length);
    });

    it("declares the gpl build, which is the prop the wrapper honours", () => {
        expect(mountEditor("").findComponent(Editor).props("licenseKey")).toBe("gpl");
    });

    it("locks the editor when the field is read only", () => {
        expect(mountEditor("", { readOnly: true }).findComponent(Editor).props("disabled")).toBe(true);
    });
});
