import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { api } from "@/api/client";
import DateField from "@/components/fields/DateField.vue";
import DateTimeField from "@/components/fields/DateTimeField.vue";
import FieldRenderer from "@/components/fields/FieldRenderer.vue";
import FieldShell from "@/components/fields/FieldShell.vue";
import FileField from "@/components/fields/FileField.vue";
import ImageField from "@/components/fields/ImageField.vue";
import JsonField from "@/components/fields/JsonField.vue";
import LookupField from "@/components/fields/LookupField.vue";
import NumberField from "@/components/fields/NumberField.vue";
import PasswordField from "@/components/fields/PasswordField.vue";
import SelectField from "@/components/fields/SelectField.vue";
import SwitchField from "@/components/fields/SwitchField.vue";
import TextField from "@/components/fields/TextField.vue";
import TextareaField from "@/components/fields/TextareaField.vue";
import TimezoneField from "@/components/fields/TimezoneField.vue";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { flushPromises, mount } from "@vue/test-utils";

function mountField(component, field, modelValue = null, extra = {}) {
    return mount(component, { props: { field, modelValue, inputId: `field-${field.name}`, ...extra } });
}

describe("FieldShell", () => {
    it("marks a required field and shows the hint", () => {
        const wrapper = mount(FieldShell, { props: { field: { name: "code", label: "field.code", required: true, hint: "field.tenantHint" }, inputId: "field-code" } });

        expect(wrapper.text()).toContain("*");
        expect(wrapper.text()).toContain("Empty means every tenant reaches it.");
    });

    it("replaces the hint with the error", () => {
        const wrapper = mount(FieldShell, { props: { field: { name: "code", label: "field.code", hint: "field.tenantHint" }, error: "Required", inputId: "field-code" } });

        expect(wrapper.text()).toContain("Required");
        expect(wrapper.text()).not.toContain("Empty means");
    });
});

describe("TextField", () => {
    it("reports what was typed and turns an empty value into nothing", async () => {
        const wrapper = mountField(TextField, { name: "code", label: "field.code" }, "acme");

        expect(wrapper.find("input").element.value).toBe("acme");

        await wrapper.find("input").setValue("blue");
        await wrapper.find("input").setValue("");

        expect(wrapper.emitted("update:modelValue")).toEqual([["blue"], [null]]);
    });

    it("honours the declared input type and the error styling", () => {
        const wrapper = mountField(TextField, { name: "email", label: "field.email", inputType: "email" }, null, { error: "Invalid" });

        expect(wrapper.find("input").attributes("type")).toBe("email");
        expect(wrapper.find("input").classes()).toContain("field-control-invalid");
    });
});

describe("TextareaField", () => {
    it("reports what was typed", async () => {
        const wrapper = mountField(TextareaField, { name: "notes", label: "field.notes" }, "hello");

        await wrapper.find("textarea").setValue("");

        expect(wrapper.emitted("update:modelValue")).toEqual([[null]]);
    });
});

describe("NumberField", () => {
    it("reports numbers and nothing for an empty value", async () => {
        const wrapper = mountField(NumberField, { name: "position", label: "field.position", min: 0 }, 2);

        await wrapper.find("input").setValue("7");
        await wrapper.find("input").setValue("");

        expect(wrapper.emitted("update:modelValue")).toEqual([[7], [null]]);
        expect(wrapper.find("input").attributes("min")).toBe("0");
    });
});

describe("SwitchField", () => {
    it("flips on click and reports its state", async () => {
        const wrapper = mountField(SwitchField, { name: "active", label: "field.active" }, false);

        expect(wrapper.attributes("aria-checked")).toBe("false");

        await wrapper.trigger("click");

        expect(wrapper.emitted("update:modelValue")).toEqual([[true]]);
    });
});

describe("SelectField", () => {
    it("lists the translated options of an enum", async () => {
        const meta = useMetaStore();
        meta.enums = { user_role: ["normal", "administrator"] };

        const wrapper = mountField(SelectField, { name: "role", label: "field.role", enumName: "user_role" }, "normal");
        const options = wrapper.findAll("option");

        expect(options).toHaveLength(3);
        expect(options.slice(1).map((option) => option.text())).toEqual(["Administrator", "Normal"]);

        await wrapper.find("select").setValue("");

        expect(wrapper.emitted("update:modelValue")).toEqual([[null]]);
    });

    it("keeps an untranslated value readable", () => {
        const meta = useMetaStore();
        meta.enums = { user_role: ["whatever"] };

        expect(mountField(SelectField, { name: "role", label: "field.role", enumName: "user_role" }).findAll("option")[1].text()).toBe("whatever");
    });
});

describe("TimezoneField", () => {
    it("lists what the api published", async () => {
        const meta = useMetaStore();
        meta.timezones = ["UTC", "America/Sao_Paulo"];

        const wrapper = mountField(TimezoneField, { name: "timezone", label: "common.timezone" }, "UTC");

        expect(wrapper.findAll("option")).toHaveLength(3);

        await wrapper.find("select").setValue("America/Sao_Paulo");

        expect(wrapper.emitted("update:modelValue")).toEqual([["America/Sao_Paulo"]]);
    });
});

describe("DateTimeField", () => {
    it("shows the instant in the timezone of the account and reports it back in utc", async () => {
        const auth = useAuthStore();
        auth.apply("abc", { id: 1, username: "root", timezone: "America/Sao_Paulo" });

        const wrapper = mountField(DateTimeField, { name: "startsAt", label: "field.startsAt" }, "2026-07-29T12:00:00Z");

        expect(wrapper.text()).toContain("America/Sao_Paulo");
        expect(wrapper.find("button").text()).toContain("9:00");

        await wrapper.find("button").trigger("click");
        await wrapper
            .findAll(".grid-cols-7 button")
            .find((day) => day.text() === "15")
            .trigger("click");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual(["2026-07-15T12:00:00.000Z"]);
    });

    it("picks the hour and the minute without leaving the popover", async () => {
        const auth = useAuthStore();
        auth.apply("abc", { id: 1, username: "root", timezone: "UTC" });

        const wrapper = mountField(DateTimeField, { name: "startsAt", label: "field.startsAt" }, "2026-07-29T12:00:00Z");

        await wrapper.find("button").trigger("click");

        const selects = wrapper.findAll("select");

        expect(selects).toHaveLength(2);
        expect(selects[0].element.value).toBe("12");

        await selects[0].setValue("18");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual(["2026-07-29T18:00:00.000Z"]);
    });

    it("stays closed and quiet when it is read only", async () => {
        const wrapper = mountField(DateTimeField, { name: "startsAt", label: "field.startsAt", readOnly: true }, "2026-07-29T12:00:00Z");

        await wrapper.find("button").trigger("click");

        expect(wrapper.findAll(".grid-cols-7 button")).toHaveLength(0);
    });
});

describe("DateField", () => {
    it("keeps a plain date free of any zone", async () => {
        const wrapper = mountField(DateField, { name: "published_at", label: "field.publishedAt" }, "2026-07-29");

        await wrapper.find("button").trigger("click");

        expect(wrapper.findAll("select")).toHaveLength(0);

        await wrapper
            .findAll(".grid-cols-7 button")
            .find((day) => day.text() === "15")
            .trigger("click");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual(["2026-07-15"]);
    });

    it("clears itself back to nothing", async () => {
        const wrapper = mountField(DateField, { name: "published_at", label: "field.publishedAt" }, "2026-07-29");

        await wrapper.find("button svg").trigger("click");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual([null]);
    });

    it("closes after a day is taken", async () => {
        const wrapper = mountField(DateField, { name: "published_at", label: "field.publishedAt" }, "2026-07-29");

        await wrapper.find("button").trigger("click");
        await wrapper
            .findAll(".grid-cols-7 button")
            .find((day) => day.text() === "15")
            .trigger("click");

        expect(wrapper.findAll(".grid-cols-7 button")).toHaveLength(0);
    });
});

describe("PasswordField", () => {
    it("hides the value until it is revealed", async () => {
        const wrapper = mountField(PasswordField, { name: "password", label: "field.password" }, "");

        expect(wrapper.find("input").attributes("type")).toBe("password");

        await wrapper.find("button").trigger("click");

        expect(wrapper.find("input").attributes("type")).toBe("text");
    });

    it("reports an empty value as nothing", async () => {
        const wrapper = mountField(PasswordField, { name: "password", label: "field.password" }, "abc");

        await wrapper.find("input").setValue("");

        expect(wrapper.emitted("update:modelValue")).toEqual([[null]]);
    });
});

describe("JsonField", () => {
    it("shows the value formatted and reports the parsed object", async () => {
        const wrapper = mountField(JsonField, { name: "meta", label: "field.metadata" }, { a: 1 });

        expect(wrapper.find("textarea").element.value).toBe('{\n  "a": 1\n}');

        await wrapper.find("textarea").setValue('{"b": 2}');
        await wrapper.find("textarea").trigger("blur");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual([{ b: 2 }]);
    });

    it("reports an empty editor as an empty object", async () => {
        const wrapper = mountField(JsonField, { name: "meta", label: "field.metadata" }, { a: 1 });

        await wrapper.find("textarea").setValue("  ");
        await wrapper.find("textarea").trigger("blur");

        expect(wrapper.emitted("update:modelValue")[0]).toEqual([{}]);
    });

    it("refuses a broken value without losing what was typed", async () => {
        const wrapper = mountField(JsonField, { name: "meta", label: "field.metadata" }, {});

        await wrapper.find("textarea").setValue("{broken");
        await wrapper.find("textarea").trigger("blur");

        expect(wrapper.emitted("update:modelValue")).toBeUndefined();
        expect(wrapper.text()).toContain("This is not a valid JSON value.");
    });

    it("formats what is readable and reports the failure otherwise", async () => {
        const wrapper = mountField(JsonField, { name: "meta", label: "field.metadata" }, {});

        await wrapper.find("textarea").setValue('{"a":1}');
        await wrapper.find("button").trigger("click");

        expect(wrapper.find("textarea").element.value).toBe('{\n  "a": 1\n}');

        await wrapper.find("textarea").setValue("{broken");
        await wrapper.find("button").trigger("click");

        expect(wrapper.text()).toContain("This is not a valid JSON value.");
    });

    it("follows the value it is given", async () => {
        const wrapper = mountField(JsonField, { name: "meta", label: "field.metadata" }, {});

        await wrapper.setProps({ modelValue: { c: 3 } });

        expect(wrapper.find("textarea").element.value).toBe('{\n  "c": 3\n}');
    });
});

describe("LookupField", () => {
    it("searches, picks and clears an option", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [{ id: 1, label: "Acme" }] });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" });

        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(wrapper.text()).toContain("Acme");

        await wrapper.findAll("li button")[0].trigger("click");

        expect(wrapper.emitted("update:modelValue")).toEqual([[1]]);

        await wrapper.setProps({ modelValue: 1 });
        await flushPromises();
        await wrapper.find("svg").trigger("click");

        expect(wrapper.emitted("update:modelValue")[1]).toEqual([null]);
    });

    it("shows what the api answered in alphabetical order", async () => {
        vi.spyOn(api, "get").mockResolvedValue({
            items: [
                { id: 1, label: "Zebra" },
                { id: 2, label: "Ébano" },
                { id: 3, label: "abacate" },
            ],
        });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" });

        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(wrapper.findAll("li button").map((option) => option.text())).toEqual(["abacate", "Ébano", "Zebra"]);
    });

    it("waits for the level above, names it and narrows the query by it", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue({ items: [{ id: 1, label: "Monthly" }] });

        const field = { name: "planId", label: "field.plan", resource: "plans", dependsOn: "integrationId" };
        const fields = [{ name: "integrationId", label: "field.integration" }, field];

        const wrapper = mount(LookupField, { props: { field, fields, values: { integrationId: null }, modelValue: null, inputId: "field-plan_id" } });

        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(wrapper.find("button").attributes("disabled")).toBeDefined();
        expect(wrapper.text()).toContain("Choose Integration first");
        expect(get).not.toHaveBeenCalled();

        await wrapper.setProps({ values: { integrationId: 4 } });
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(get).toHaveBeenCalledWith("/plans/lookup", { search: "", limit: 20, integrationId: 4 });
        expect(wrapper.text()).toContain("Monthly");
    });

    it("lists again when the level above moves", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue({ items: [{ id: 1, label: "Monthly" }] });

        const field = { name: "planId", label: "field.plan", resource: "plans", dependsOn: "integrationId" };
        const wrapper = mount(LookupField, { props: { field, fields: [field], values: { integrationId: 4 }, modelValue: null, inputId: "field-plan_id" } });

        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        get.mockResolvedValue({ items: [{ id: 2, label: "Yearly" }] });
        await wrapper.setProps({ values: { integrationId: 9 } });
        await flushPromises();

        expect(get).toHaveBeenLastCalledWith("/plans/lookup", { search: "", limit: 20, integrationId: 9 });
        expect(wrapper.text()).toContain("Yearly");
    });

    it("names by its number a record the api cannot name", async () => {
        vi.spyOn(api, "get").mockRejectedValue(new Error("404"));

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" }, 9);

        await flushPromises();

        expect(wrapper.text()).toContain("#9");
    });

    it("names the value it holds even when the options do not carry it", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue({ id: 90, label: "Ninetieth tenant" });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" }, 90);

        await flushPromises();

        expect(get).toHaveBeenCalledWith("/tenants/lookup/90");
        expect(wrapper.text()).toContain("Ninetieth tenant");
    });

    it("says when nothing was found", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [] });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" });

        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(wrapper.text()).toContain("No option found.");
    });

    it("stays shut while it is read only", async () => {
        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants", readOnly: true });

        await wrapper.find("button").trigger("click");

        expect(wrapper.find("ul").exists()).toBe(false);
    });

    it("searches again after the typing settles", async () => {
        vi.useFakeTimers();

        const request = vi.spyOn(api, "get").mockResolvedValue({ items: [] });
        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" });

        await wrapper.find("button").trigger("click");
        await wrapper.find("input").setValue("ac");

        vi.advanceTimersByTime(300);
        await nextTick();

        expect(request.mock.calls.at(-1)[1]).toMatchObject({ search: "ac" });

        vi.useRealTimers();
    });

    it("closes when the click lands outside", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [] });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" }, null, { attachTo: document.body });

        await wrapper.find("button").trigger("click");
        expect(wrapper.find("ul").exists()).toBe(true);

        document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        await nextTick();

        expect(wrapper.find("ul").exists()).toBe(false);

        wrapper.unmount();
    });
});

function pickFile(wrapper, name = "cover.png") {
    const input = wrapper.find("input[type=file]");

    Object.defineProperty(input.element, "files", { value: [new File(["x"], name)], configurable: true });

    return input.trigger("change");
}

describe("ImageField", () => {
    it("stores the file and reports its key", async () => {
        vi.spyOn(api, "upload").mockResolvedValue({ key: "images/one.png", url: "/media/images/one.png" });

        const wrapper = mountField(ImageField, { name: "image", label: "field.image", purpose: "product-image" });

        await pickFile(wrapper);
        await flushPromises();

        expect(wrapper.emitted("update:modelValue")).toEqual([["images/one.png"]]);
    });

    it("previews and removes what is stored", async () => {
        const meta = useMetaStore();
        meta.storageBaseUrl = "/media";

        const wrapper = mountField(ImageField, { name: "image", label: "field.image", purpose: "product-image" }, "images/one.png");

        expect(wrapper.find("img").attributes("src")).toBe("/media/images/one.png");

        await wrapper.find("button").trigger("click");

        expect(wrapper.emitted("update:modelValue")).toEqual([[null]]);
    });

    it("reports what the api refused", async () => {
        vi.spyOn(api, "upload").mockRejectedValue({ errors: { file: "This file type is not accepted." }, message: "broken" });

        const wrapper = mountField(ImageField, { name: "image", label: "field.image", purpose: "product-image" });

        await pickFile(wrapper);
        await flushPromises();

        expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    });

    it("ignores an empty selection", async () => {
        const upload = vi.spyOn(api, "upload");
        const wrapper = mountField(ImageField, { name: "image", label: "field.image", purpose: "product-image" });

        await wrapper.find("input[type=file]").trigger("change");

        expect(upload).not.toHaveBeenCalled();
    });
});

describe("FileField", () => {
    it("offers what the field declares when it depends on nothing", () => {
        const wrapper = mount(FileField, { props: { field: { name: "file", label: "field.file", purpose: "product-file", accept: ".pdf,.epub,.zip" }, modelValue: null, inputId: "file" } });

        expect(wrapper.find("input[type=file]").attributes("accept")).toBe(".pdf,.epub,.zip");
    });

    it("offers everything when nothing narrows it", () => {
        const wrapper = mount(FileField, { props: { field: { name: "file", label: "field.file", purpose: "product-file" }, modelValue: null, inputId: "asset" } });

        expect(wrapper.find("input[type=file]").attributes("accept")).toBeUndefined();
    });

    it("stores the file and shows its name", async () => {
        const meta = useMetaStore();
        meta.storageBaseUrl = "/media";

        vi.spyOn(api, "upload").mockResolvedValue({ key: "files/book.epub" });

        const wrapper = mountField(FileField, { name: "file", label: "field.file", purpose: "product-file" });

        await pickFile(wrapper, "book.epub");
        await flushPromises();

        expect(wrapper.emitted("update:modelValue")).toEqual([["files/book.epub"]]);

        await wrapper.setProps({ modelValue: "files/book.epub" });

        expect(wrapper.find("a").text()).toBe("book.epub");
    });

    it("removes what is stored", async () => {
        const wrapper = mountField(FileField, { name: "file", label: "field.file", purpose: "product-file" }, "files/book.epub");

        await wrapper.findAll("button")[0].trigger("click");

        expect(wrapper.emitted("update:modelValue")).toEqual([[null]]);
    });

    it("reports what the api refused", async () => {
        vi.spyOn(api, "upload").mockRejectedValue({ message: "broken" });

        const wrapper = mountField(FileField, { name: "file", label: "field.file", purpose: "product-file" });

        await pickFile(wrapper, "book.epub");
        await flushPromises();

        expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    });

    it("ignores an empty selection", async () => {
        const upload = vi.spyOn(api, "upload");
        const wrapper = mountField(FileField, { name: "file", label: "field.file", purpose: "product-file" });

        await wrapper.find("input[type=file]").trigger("change");

        expect(upload).not.toHaveBeenCalled();
    });
});

describe("FieldRenderer", () => {
    it("picks the component of each declared type", () => {
        const meta = useMetaStore();
        meta.enums = { user_role: ["normal"] };
        meta.timezones = ["UTC"];

        expect(
            mount(FieldRenderer, { props: { field: { name: "code", label: "field.code", type: "text" } } })
                .find("input")
                .exists(),
        ).toBe(true);
        expect(
            mount(FieldRenderer, { props: { field: { name: "notes", label: "field.notes", type: "textarea" } } })
                .find("textarea")
                .exists(),
        ).toBe(true);
        expect(
            mount(FieldRenderer, { props: { field: { name: "role", label: "field.role", type: "select", enumName: "user_role" } } })
                .find("select")
                .exists(),
        ).toBe(true);
        expect(
            mount(FieldRenderer, { props: { field: { name: "active", label: "field.active", type: "switch" }, modelValue: false } })
                .find("[role=switch]")
                .exists(),
        ).toBe(true);
    });

    it("draws nothing at all for a type nobody wrote a component for", () => {
        // Substituting a text box would hide the mistake behind a field that looks like it works.
        expect(
            mount(FieldRenderer, { props: { field: { name: "code", label: "field.code", type: "whatever" } } })
                .find("input")
                .exists(),
        ).toBe(false);
    });

    it("gives the wide types the whole row", () => {
        expect(mount(FieldRenderer, { props: { field: { name: "meta", label: "field.metadata", type: "json" }, modelValue: {} } }).classes()).toContain("sm:col-span-2");
        expect(mount(FieldRenderer, { props: { field: { name: "code", label: "field.code", type: "text" } } }).classes()).not.toContain("sm:col-span-2");
    });

    it("passes what the field reports up", async () => {
        const wrapper = mount(FieldRenderer, { props: { field: { name: "code", label: "field.code", type: "text" } } });

        await wrapper.find("input").setValue("acme");

        expect(wrapper.emitted("update:modelValue")).toEqual([["acme"]]);
    });
});

describe("every field component", () => {
    const FIELDS = readdirSync("src/components/fields").filter((name) => name.endsWith("Field.vue"));

    it("is one this guard reads", () => {
        expect(FIELDS.length).toBeGreaterThan(10);
    });

    it("declares the same four the renderer hands it, so one of them cannot quietly stop marking itself invalid", () => {
        const missing = [];

        for (const name of FIELDS) {
            const source = readFileSync(`src/components/fields/${name}`, "utf8");
            const declared = [...source.matchAll(/^ {4}(\w+): \{/gm)].map((found) => found[1]);

            missing.push(...["field", "modelValue", "error", "inputId"].filter((prop) => !declared.includes(prop)).map((prop) => `${name}: ${prop}`));
        }

        expect(missing).toEqual([]);
    });

    it("reads every prop it declares, because one nobody reads is one somebody pasted", () => {
        const unread = [];

        for (const name of FIELDS) {
            const source = readFileSync(`src/components/fields/${name}`, "utf8");
            const declared = [...source.matchAll(/^ {4}(\w+): \{/gm)].map((found) => found[1]);
            const body = source.replace(/defineProps\(\{[\s\S]*?\n\}\)/, "");

            unread.push(...declared.filter((prop) => !new RegExp(`\\b${prop}\\b`).test(body)).map((prop) => `${name}: ${prop}`));
        }

        expect(unread).toEqual([]);
    });
});

describe("every control of the panel", () => {
    // A placeholder disappears the moment somebody types, so it is never the name of a control.
    it("is named by a label or by aria-label", () => {
        const walk = (folder) =>
            readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
                const full = `${folder}/${entry.name}`;

                return entry.isDirectory() ? walk(full) : entry.name.endsWith(".vue") ? [full] : [];
            });

        const anonymous = [];
        let read = 0;

        for (const path of walk("src")) {
            for (const tag of readFileSync(path, "utf8").match(/<(?:input|select|textarea)\b[^>]*>/gs) || []) {
                if (tag.includes('type="hidden"')) {
                    continue;
                }

                read += 1;

                if (!/\s:?id=/.test(tag) && !/\s:?aria-label=/.test(tag)) {
                    anonymous.push(`${path.split("/").pop()}: ${tag.slice(0, 60)}`);
                }
            }
        }

        expect(read).toBeGreaterThan(10);
        expect(anonymous).toEqual([]);
    });
});

describe("a control the form refused", () => {
    const MARKED = readdirSync("src/components/fields").filter((name) => name.endsWith(".vue") && readFileSync(`src/components/fields/${name}`, "utf8").includes("field-control-invalid"));

    it("says so wherever a control turns red", () => {
        expect(MARKED.length).toBeGreaterThanOrEqual(8);

        const silent = MARKED.filter((name) => !/v-bind="(refused|names)\(inputId, (error|invalid)\)"/.test(readFileSync(`src/components/fields/${name}`, "utf8")));

        expect(silent).toEqual([]);
    });

    it("names the message the shell drew", () => {
        const shell = mount(FieldShell, { props: { field: { name: "email", label: "field.email" }, error: "Not an address", inputId: "field-email" } });

        expect(shell.find("p.text-danger").attributes("id")).toBe("field-email-error");

        const input = mountField(TextField, { name: "email", label: "field.email" }, null, { error: "Not an address" }).find("input");

        expect(input.attributes("aria-invalid")).toBe("true");
        expect(input.attributes("aria-describedby")).toBe("field-email-error");
    });

    it("leaves the invalid state off a role that has none", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [] });

        const wrapper = mountField(LookupField, { name: "tenantId", label: "field.tenant", resource: "tenants" }, null, { error: "Pick one" });

        await flushPromises();

        const button = wrapper.find("button");

        expect(button.attributes("aria-describedby")).toBe("field-tenantId-error");
        expect(button.attributes("aria-invalid")).toBeUndefined();
    });
});
