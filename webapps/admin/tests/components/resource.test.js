import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTestRouter } from "../helpers/router";
import { api } from "@/api/client";
import AppShell from "@/components/layout/AppShell.vue";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import DeleteConfirm from "@/components/resource/DeleteConfirm.vue";
import FieldGroup from "@/components/resource/FieldGroup.vue";
import ResourceFilters from "@/components/resource/ResourceFilters.vue";
import SubitemManager from "@/components/resource/SubitemManager.vue";
import { LOCALE_STORAGE_KEY } from "@/i18n";
import { RESOURCES } from "@/resources";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import { flushPromises, mount } from "@vue/test-utils";

const GROUP = {
    key: "identification",
    fields: [
        { name: "name", label: "field.name", type: "text" },
        { name: "active", label: "field.active", type: "switch" },
    ],
};

describe("FieldGroup", () => {
    it("renders every field of the group under its title", () => {
        const wrapper = mount(FieldGroup, { props: { group: GROUP, values: { name: "Acme", active: true } } });

        expect(wrapper.find("h2").text()).toBe("Identification");
        expect(wrapper.find("input").element.value).toBe("Acme");
        expect(wrapper.find("[role=switch]").attributes("aria-checked")).toBe("true");
    });

    it("reports which field changed", async () => {
        const wrapper = mount(FieldGroup, { props: { group: GROUP, values: { name: "", active: false } } });

        await wrapper.find("input").setValue("Blue");

        expect(wrapper.emitted("change")[0]).toEqual(["name", "Blue"]);
    });

    it("shows the error of a field", () => {
        const wrapper = mount(FieldGroup, { props: { group: GROUP, values: { name: "" }, errors: { name: "Required" } } });

        expect(wrapper.text()).toContain("Required");
    });
});

const FILTERS = [
    { name: "role", label: "field.role", type: "enum", enumName: "user_role" },
    { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
    { name: "active", label: "field.active", type: "boolean" },
];

describe("ResourceFilters", () => {
    it("renders one control per filter plus the search", () => {
        const meta = useMetaStore();
        meta.enums = { user_role: ["normal"] };

        const wrapper = mount(ResourceFilters, { props: { filters: FILTERS, values: { role: null, tenantId: null, active: null } } });

        expect(wrapper.find("#filter-search").exists()).toBe(true);
        expect(wrapper.find("#field-role").exists()).toBe(true);
        expect(wrapper.find("#field-tenantId").exists()).toBe(true);
        expect(wrapper.find("#field-active").exists()).toBe(true);
    });

    it("reports the search and each filter", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ items: [] });

        const wrapper = mount(ResourceFilters, { props: { filters: FILTERS, values: { role: null, tenantId: null, active: null } } });

        await wrapper.find("#filter-search").setValue("ada");
        await wrapper.find("#field-active").setValue("true");

        expect(wrapper.emitted("update:search")[0]).toEqual(["ada"]);
        expect(wrapper.emitted("change")[0]).toEqual(["active", "true"]);
    });

    it("reports an emptied boolean filter as nothing", async () => {
        const wrapper = mount(ResourceFilters, { props: { filters: [FILTERS[2]], values: { active: "true" } } });

        await wrapper.find("#field-active").setValue("");

        expect(wrapper.emitted("change")[0]).toEqual(["active", null]);
    });

    it("offers to clear only while something narrows the list", async () => {
        const clean = mount(ResourceFilters, { props: { filters: [FILTERS[2]], values: { active: null } } });

        expect(clean.text()).not.toContain("Clear filters");

        const narrowed = mount(ResourceFilters, { props: { filters: [FILTERS[2]], values: { active: "true" } } });

        await narrowed.find("button").trigger("click");

        expect(narrowed.emitted("clear")).toHaveLength(1);
    });

    it("counts the search as a narrowing", () => {
        expect(mount(ResourceFilters, { props: { filters: [], values: {}, search: "ada" } }).text()).toContain("Clear filters");
    });
});

describe("DeleteConfirm", () => {
    it("asks once and says what goes with the record", () => {
        const wrapper = mount(DeleteConfirm, { props: { open: true } });

        expect(wrapper.text()).toContain("Delete this record?");
        expect(wrapper.text()).toContain("Are you sure? The related data and the attached files are removed with it");
    });

    it("confirms and closes", async () => {
        const wrapper = mount(DeleteConfirm, { props: { open: true } });
        const [cancel, remove] = wrapper.findAll("footer button");

        await cancel.trigger("click");
        await remove.trigger("click");

        expect(wrapper.emitted("close")).toHaveLength(1);
        expect(wrapper.emitted("confirm")).toHaveLength(1);
    });
});

describe("AppSidebar", () => {
    async function mountSidebar(path = "/") {
        const router = createTestRouter(path);
        await router.isReady();

        usePermissionsStore().reachable = RESOURCES.map((resource) => resource.name);

        return mount(AppSidebar, { global: { plugins: [router] } });
    }

    it("shows the name and the version the api reports", async () => {
        const meta = useMetaStore();
        meta.name = "Acme Panel";
        meta.version = "1.4.2";

        const wrapper = await mountSidebar();

        expect(wrapper.text()).toContain("Acme Panel");
        expect(wrapper.text()).toContain("v1.4.2");
    });

    it("lists every resource of a section, and only the ones a parent does not manage", async () => {
        const wrapper = await mountSidebar();
        const listed = RESOURCES.filter((resource) => !resource.managedByParent);

        expect(wrapper.text()).toContain("Access");
        expect(wrapper.text()).toContain("Users");
        expect(wrapper.findAll("nav a")).toHaveLength(listed.length + 1);
    });

    it("leaves out the resources only reached inside their parent", async () => {
        const wrapper = await mountSidebar();

        expect(wrapper.text()).not.toContain("Catalog Items");
        expect(wrapper.text()).not.toContain("Schedule Items");
        expect(wrapper.text()).not.toContain("Benefit Grants");
    });

    it("closes the drawer when a link is taken", async () => {
        const wrapper = await mountSidebar();
        const ui = useUiStore();

        ui.toggleSidebar(true);
        await wrapper.findAll("nav a")[0].trigger("click");

        expect(ui.sidebarOpen).toBe(false);
    });
});

describe("AppTopbar", () => {
    let router;

    beforeEach(() => {
        router = createTestRouter();
    });

    it("shows who is signed in", () => {
        const auth = useAuthStore();
        auth.apply("abc", { id: 1, username: "root" });

        expect(mount(AppTopbar, { global: { plugins: [router] } }).text()).toContain("root");
    });

    it("keeps the chosen locale", async () => {
        const wrapper = mount(AppTopbar, { global: { plugins: [router] } });

        await wrapper.find("select").setValue("pt");

        expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("pt");
    });

    it("signs out and goes back to the login", async () => {
        const push = vi.spyOn(router, "push");
        const auth = useAuthStore();

        auth.apply("abc", { id: 1, username: "root" });

        const wrapper = mount(AppTopbar, { global: { plugins: [router] } });

        await wrapper.findAll("button").at(-1).trigger("click");

        expect(auth.isSignedIn).toBe(false);
        expect(push).toHaveBeenCalledWith({ name: "login" });
    });

    it("opens the drawer", async () => {
        const wrapper = mount(AppTopbar, { global: { plugins: [router] } });
        const ui = useUiStore();

        await wrapper.find("button").trigger("click");

        expect(ui.sidebarOpen).toBe(true);
    });
});

describe("AppShell", () => {
    // The sidebar draws thirty one links before the content, and a keyboard would walk them on every screen.
    it("puts the way to the content before everything else", () => {
        const wrapper = mount(AppShell, { global: { plugins: [createTestRouter("/")] } });
        const skip = wrapper.find('a[href="#content"]');

        expect(skip.exists()).toBe(true);
        expect(skip.classes()).toContain("sr-only");
        expect(wrapper.find("main").attributes("id")).toBe("content");
    });

    let router;

    beforeEach(() => {
        router = createTestRouter();
    });

    it("renders the header and the body it is given", () => {
        const wrapper = mount(AppShell, { slots: { header: "<h1>Users</h1>", default: "<p>body</p>" }, global: { plugins: [router] } });

        expect(wrapper.text()).toContain("Users");
        expect(wrapper.text()).toContain("body");
    });

    it("keeps the scroll inside the content area", () => {
        const wrapper = mount(AppShell, { global: { plugins: [router] } });
        const main = wrapper.find("main");

        // The `min-h-0` lets the column shrink and the `relative` anchors the sr-only elements, and both keep the page from scrolling.
        expect(main.classes()).toEqual(expect.arrayContaining(["overflow-y-auto", "min-h-0", "relative"]));
        expect(main.element.parentElement.className).toContain("min-h-0");
    });

    it("mounts the drawer only while it is open", async () => {
        const wrapper = mount(AppShell, { global: { plugins: [router] } });
        const ui = useUiStore();

        expect(wrapper.findAllComponents(AppSidebar)).toHaveLength(1);

        ui.toggleSidebar(true);
        await flushPromises();

        expect(wrapper.findAllComponents(AppSidebar)).toHaveLength(2);

        await wrapper.find(".bg-inverse\\/50").trigger("click");

        expect(ui.sidebarOpen).toBe(false);
    });
});

describe("SubitemManager", () => {
    let router;

    beforeEach(async () => {
        router = createTestRouter("/galleries/7/edit");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ items: [] });
    });

    function panel() {
        return mount(SubitemManager, {
            props: { subitem: { resource: "gallery-photos", foreignKey: "galleryId" }, parentId: "7" },
            global: { plugins: [router] },
        });
    }

    it("starts a child already knowing which parent it belongs to", async () => {
        const wrapper = panel();
        await flushPromises();

        await wrapper.find("button").trigger("click");
        await flushPromises();

        // A field that hangs off the parent would wait forever without it, and the panel never shows the parent.
        expect(wrapper.vm.values.galleryId).toBe(7);
    });

    it("asks the api only for the children of that parent", async () => {
        panel();
        await flushPromises();

        expect(api.get).toHaveBeenCalledWith("/gallery-photos", { limit: 100, galleryId: "7" });
    });

    it("says so and stops offering an order when it could not draw the whole set", async () => {
        // A partial order renumbers what was drawn and leaves the rest where it was, which shuffles rows nobody could see.
        api.get.mockResolvedValue({ items: [{ id: 3, caption: "Reception", position: 0 }], count: 140 });

        const wrapper = mount(SubitemManager, {
            props: { subitem: { resource: "gallery-photos", foreignKey: "galleryId", orderBy: "position" }, parentId: "7" },
            global: { plugins: [router] },
        });

        await flushPromises();

        expect(wrapper.text()).toContain("Showing 1 of 140");
        expect(wrapper.find("[title='Move up']").exists()).toBe(false);
    });

    it("offers the order once it holds every child there is", async () => {
        api.get.mockResolvedValue({
            items: [
                { id: 3, caption: "Reception", position: 0 },
                { id: 4, caption: "The desk", position: 1 },
            ],
            count: 2,
        });

        const wrapper = mount(SubitemManager, {
            props: { subitem: { resource: "gallery-photos", foreignKey: "galleryId", orderBy: "position" }, parentId: "7" },
            global: { plugins: [router] },
        });

        await flushPromises();

        expect(wrapper.text()).not.toContain("Showing");
        expect(wrapper.find("[title='Move up']").exists()).toBe(true);
    });

    it("opens a child already filled with what it holds", async () => {
        api.get.mockResolvedValue({ items: [{ id: 3, caption: "Reception", position: 0 }] });

        const wrapper = panel();
        await flushPromises();

        await wrapper.find("li [title='Edit']").trigger("click");
        await flushPromises();

        // Without this the modal would open blank and saving would wipe what the row already had.
        expect(wrapper.vm.values.caption).toBe("Reception");
        expect(wrapper.vm.editing.id).toBe(3);
    });

    it("writes an edited child back over itself instead of adding another", async () => {
        api.get.mockResolvedValue({ items: [{ id: 3, caption: "Reception" }] });

        const put = vi.spyOn(api, "put").mockResolvedValue({ id: 3 });
        const post = vi.spyOn(api, "post").mockResolvedValue({ id: 99 });

        const wrapper = panel();
        await flushPromises();

        await wrapper.find("li [title='Edit']").trigger("click");
        await flushPromises();
        await wrapper.vm.save();

        expect(put).toHaveBeenCalledWith("/gallery-photos/3", expect.objectContaining({ galleryId: "7" }));
        expect(post).not.toHaveBeenCalled();
    });

    it("offers a row only what the resource allows doing to it", async () => {
        // The ledger is append only, so its panel shows no way to edit or remove a line.
        api.get.mockResolvedValue({ items: [{ id: 3, wallet: "gold", amount: 10 }] });

        const wrapper = mount(SubitemManager, {
            props: { subitem: { resource: "credit-transactions", foreignKey: "userId" }, parentId: "7" },
            global: { plugins: [router] },
        });

        await flushPromises();

        expect(wrapper.find("li [title='Edit']").exists()).toBe(false);
        expect(wrapper.find("li [title='Delete']").exists()).toBe(false);
    });

    it("still adds a new child when nothing is being edited", async () => {
        const post = vi.spyOn(api, "post").mockResolvedValue({ id: 99 });

        const wrapper = panel();
        await flushPromises();

        await wrapper.find("button").trigger("click");
        await flushPromises();
        await wrapper.vm.save();

        expect(post).toHaveBeenCalledWith("/gallery-photos", expect.objectContaining({ galleryId: "7" }));
    });
});
