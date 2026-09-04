import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { createTestRouter } from "../helpers/router";
import { api } from "@/api/client";
import FileField from "@/components/fields/FileField.vue";
import ImageField from "@/components/fields/ImageField.vue";
import JsonField from "@/components/fields/JsonField.vue";
import LookupField from "@/components/fields/LookupField.vue";
import NumberField from "@/components/fields/NumberField.vue";
import PasswordField from "@/components/fields/PasswordField.vue";
import SelectField from "@/components/fields/SelectField.vue";
import TextField from "@/components/fields/TextField.vue";
import TextareaField from "@/components/fields/TextareaField.vue";
import TimezoneField from "@/components/fields/TimezoneField.vue";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import DataGrid from "@/components/ui/DataGrid.vue";
import ToastStack from "@/components/ui/ToastStack.vue";
import { RESOURCES, canCreate, canDelete, canEdit, canView } from "@/resources";
import { USER_STORAGE_KEY, useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import { fromInputDateTime, resolveTimezone } from "@/support/datetime";
import { flushPromises, mount } from "@vue/test-utils";

describe("empty values of every field", () => {
    it("renders an empty control instead of a missing one", () => {
        const meta = useMetaStore();
        meta.enums = { user_role: ["normal"] };
        meta.timezones = ["UTC"];

        expect(mount(TextField, { props: { field: { name: "code", label: "field.code" }, modelValue: null, inputId: "a" } }).find("input").element.value).toBe("");
        expect(mount(TextareaField, { props: { field: { name: "notes", label: "field.notes" }, modelValue: null, inputId: "b" } }).find("textarea").element.value).toBe("");
        expect(mount(NumberField, { props: { field: { name: "position", label: "field.position" }, modelValue: null, inputId: "c" } }).find("input").element.value).toBe("");
        expect(mount(PasswordField, { props: { field: { name: "password", label: "field.password" }, modelValue: null, inputId: "d" } }).find("input").element.value).toBe("");
        expect(mount(SelectField, { props: { field: { name: "role", label: "field.role", enumName: "user_role" }, modelValue: null, inputId: "e" } }).find("select").element.value).toBe("");
        expect(mount(TimezoneField, { props: { field: { name: "timezone", label: "common.timezone" }, modelValue: null, inputId: "f" } }).find("select").element.value).toBe("");
    });

    it("shows no file link while nothing is stored", () => {
        const wrapper = mount(FileField, { props: { field: { name: "file", label: "field.file", purpose: "product-file" }, modelValue: null, inputId: "g" } });

        expect(wrapper.find("a").exists()).toBe(false);
    });

    it("shows no preview while no image is stored", () => {
        const wrapper = mount(ImageField, { props: { field: { name: "image", label: "field.image", purpose: "product-image" }, modelValue: null, inputId: "h" } });

        expect(wrapper.find("img").exists()).toBe(false);
    });

    it("treats a missing json value as an empty object", () => {
        const wrapper = mount(JsonField, { props: { field: { name: "meta", label: "field.metadata" }, modelValue: null, inputId: "i" } });

        expect(wrapper.find("textarea").element.value).toBe("{}");
    });

    it("formats an empty json editor into an empty object", async () => {
        const wrapper = mount(JsonField, { props: { field: { name: "meta", label: "field.metadata" }, modelValue: {}, inputId: "j" } });

        await wrapper.find("textarea").setValue("");
        await wrapper.find("button").trigger("click");

        expect(wrapper.find("textarea").element.value).toBe("{}");
    });

    it("leaves the json draft alone when the value it is given matches", async () => {
        const wrapper = mount(JsonField, { props: { field: { name: "meta", label: "field.metadata" }, modelValue: { a: 1 }, inputId: "k" } });

        const before = wrapper.find("textarea").element.value;

        await wrapper.setProps({ modelValue: { a: 1 } });

        expect(wrapper.find("textarea").element.value).toBe(before);
    });
});

describe("LookupField", () => {
    it("clears the selection it is given", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [{ id: 1, label: "Acme" }] });

        const wrapper = mount(LookupField, { props: { field: { name: "tenantId", label: "field.tenant", resource: "tenants" }, modelValue: null, inputId: "l" } });

        await flushPromises();

        expect(wrapper.text()).toContain("Select");
    });
});

describe("ToastStack", () => {
    it("draws every tone the store can raise", async () => {
        const wrapper = mount(ToastStack);
        const ui = useUiStore();

        ui.success("done");
        ui.error("broken");
        ui.info("hello");
        await nextTick();

        expect(wrapper.html()).toContain("bg-good-fill");
        expect(wrapper.html()).toContain("bg-danger-fill");
        expect(wrapper.html()).toContain("bg-inverse");
    });
});

describe("AppSidebar", () => {
    async function mountSidebar(path = "/") {
        const router = createTestRouter(path);
        await router.isReady();

        usePermissionsStore().reachable = RESOURCES.map((resource) => resource.name);

        return mount(AppSidebar, { global: { plugins: [router] } });
    }

    it("closes the drawer when a resource link is taken", async () => {
        const wrapper = await mountSidebar();
        const ui = useUiStore();

        ui.toggleSidebar(true);
        await wrapper.findAll("nav a").at(-1).trigger("click");

        expect(ui.sidebarOpen).toBe(false);
    });

    it("marks the dashboard only on the dashboard", async () => {
        const wrapper = await mountSidebar("/");
        const marked = wrapper.findAll("nav a.border-brand-500");

        expect(marked).toHaveLength(1);
        expect(marked[0].text()).toContain("Dashboard");
    });

    it("keeps the resource marked while a record of it is open", async () => {
        for (const path of ["/tenants", "/tenants/new", "/tenants/7", "/tenants/7/edit"]) {
            const wrapper = await mountSidebar(path);
            const marked = wrapper.findAll("nav a.border-brand-500");

            expect(marked, path).toHaveLength(1);
            expect(marked[0].text(), path).toContain("Tenants");
        }
    });

    it("marks nothing when the route belongs to no resource", async () => {
        const wrapper = await mountSidebar("/login");

        expect(wrapper.findAll("nav a.border-brand-500")).toHaveLength(0);
    });
});

describe("DataGrid", () => {
    it("opens a record from the compact layout", async () => {
        const records = [{ id: 1, code: "acme", name: "Acme" }];
        const wrapper = mount(DataGrid, { props: { columns: [{ name: "code", label: "field.code" }], records, emptyMessage: "empty" } });

        await wrapper.find("ul li button").trigger("click");

        expect(wrapper.emitted("edit")[0]).toEqual([records[0]]);
    });

    it("keeps the compact card inert when it leads nowhere", async () => {
        const records = [{ id: 1, code: "acme", name: "Acme" }];
        const wrapper = mount(DataGrid, { props: { columns: [{ name: "code", label: "field.code" }], records, emptyMessage: "empty", canView: false, canEdit: false, canDelete: false } });

        const card = wrapper.find("ul li > div");

        await card.trigger("click");

        expect(card.exists()).toBe(true);
        expect(wrapper.emitted("view")).toBeUndefined();
        expect(wrapper.emitted("edit")).toBeUndefined();
    });

    it("hides the write actions of the compact layout", () => {
        const wrapper = mount(DataGrid, { props: { columns: [{ name: "code", label: "field.code" }], records: [{ id: 1, code: "acme" }], emptyMessage: "empty", canEdit: false, canDelete: false } });

        expect(wrapper.findAll("ul li button")).toHaveLength(2);
    });
});

describe("auth store", () => {
    it("survives a broken account in storage", () => {
        localStorage.setItem(USER_STORAGE_KEY, "{not json");

        expect(useAuthStore().user).toBeNull();
    });
});

describe("resource permissions", () => {
    it("honours a resource that closes a single action", () => {
        expect(canView({ canView: false })).toBe(false);
        expect(canCreate({ canCreate: false })).toBe(false);
        expect(canEdit({ canEdit: false })).toBe(false);
        expect(canDelete({ canDelete: false })).toBe(false);
    });

    it("keeps reading open by default", () => {
        expect(canView({})).toBe(true);
    });
});

describe("datetime support", () => {
    it("reads the timezone of the browser when none is preferred", () => {
        expect(resolveTimezone(undefined)).toBeTruthy();
    });

    it("corrects a wall clock that lands on a daylight saving jump", () => {
        // The clock skips 02:30 in New York that night, so it settles on the offset in force before it.
        expect(fromInputDateTime("2026-03-08T02:30", "America/New_York")).toBe("2026-03-08T06:30:00.000Z");
    });
});
