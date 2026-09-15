import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { nextTick, reactive } from "vue";

import { i18n } from "../setup";
import { api } from "@/api/client";
import HtmlField from "@/components/fields/HtmlField.vue";
import { useMetaStore } from "@/stores/meta";
import { useThemeStore } from "@/stores/theme";
import { HOLDS } from "@/support/holds";
import Editor from "@tinymce/tinymce-vue";
import { mount } from "@vue/test-utils";

function mountEditor(modelValue = "", field = {}, holds = reactive(new Set())) {
    return mount(HtmlField, { props: { field: { name: "description", label: "field.description", ...field }, modelValue, inputId: "field-description" }, global: { provide: { [HOLDS]: holds } } });
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
    });

    it("turns the page it writes on with the palette, and stays the same editor while it does", async () => {
        // Building it again left Vue inserting beside a node the editor had moved, and the field vanished on the first turn.
        const theme = useThemeStore();
        const wrapper = mountEditor("");
        const editor = wrapper.findComponent(Editor);
        const page = document.implementation.createHTMLDocument("");

        configurationOf(wrapper).setup({ on: (event, ready) => event === "init" && ready(), getDoc: () => page });
        await nextTick();

        expect(page.head.querySelector("style").textContent).toContain("color-scheme: light");

        theme.chosen = "dark";
        await nextTick();

        expect(page.head.querySelectorAll("style")).toHaveLength(1);
        expect(page.head.querySelector("style").textContent).toContain("color-scheme: dark");
        expect(wrapper.findComponent(Editor).vm).toBe(editor.vm);
    });

    it("builds the editor again in another language, because it reads its init once", async () => {
        const wrapper = mountEditor("");
        const editor = wrapper.findComponent(Editor).vm;

        i18n.global.locale.value = "pt";
        await nextTick();

        expect(wrapper.findComponent(Editor).vm).not.toBe(editor);
        expect(configurationOf(wrapper).language).toBe("pt_BR");
    });

    it("bundles exactly the plugins it turns on", () => {
        // Twelve plugins were imported and never named in the configuration, which is weight every visit to a form carried for nothing.
        const source = readFileSync("src/components/fields/HtmlField.vue", "utf8");
        const imported = [...source.matchAll(/import "tinymce\/plugins\/(\w+)";/g)].map((found) => found[1]).sort();

        expect(imported).toEqual(configurationOf(mountEditor("")).plugins.split(" ").sort());
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

    it("takes a picture the api refused out of the text and lets the form go", async () => {
        vi.spyOn(api, "upload").mockRejectedValue({ message: "This file is not a readable image." });

        const holds = reactive(new Set());
        const configuration = configurationOf(mountEditor("", {}, holds));

        await expect(configuration.images_upload_handler({ blob: () => new Blob(["x"]), filename: () => "one.png" })).rejects.toEqual({ message: "This file is not a readable image.", remove: true });
        expect(holds.size).toBe(0);
    });

    it("holds the form while any pasted picture is still on its way up", async () => {
        // Saving before the answer would store the address of a blob that lives in this tab only.
        let answer;
        vi.spyOn(api, "upload").mockImplementation(() => new Promise((resolve) => (answer = resolve)));

        const holds = reactive(new Set());
        const configuration = configurationOf(mountEditor("", {}, holds));
        const uploading = configuration.images_upload_handler({ blob: () => new Blob(["x"]), filename: () => "one.png" });

        expect(holds.size).toBe(1);

        answer({ key: "images/content/one.png" });
        await uploading;

        expect(holds.size).toBe(0);
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
