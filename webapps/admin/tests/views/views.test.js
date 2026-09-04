import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTestRouter } from "../helpers/router";
import App from "@/App.vue";
import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";
import NotFoundView from "@/views/NotFoundView.vue";
import ResourceDetailView from "@/views/ResourceDetailView.vue";
import ResourceFormView from "@/views/ResourceFormView.vue";
import ResourceListView from "@/views/ResourceListView.vue";
import { flushPromises, mount } from "@vue/test-utils";

const TENANT = { id: 1, code: "acme", name: "Acme", domain: "acme.test", title: null, email_contact: null, email_administrative: null, active: true, meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" };

function mountView(component, router) {
    return mount(component, { global: { plugins: [router] } });
}

// The lookup draws its panel outside the field, so its options are looked for across the tree.
async function chooseOption(wrapper, index = 0) {
    await wrapper.findAll("div.fixed li button")[index].trigger("click");
    await flushPromises();
}

describe("LoginView", () => {
    let router;

    beforeEach(() => {
        router = createTestRouter("/login");
        vi.spyOn(api, "get").mockResolvedValue({ provider: "disabled", token: "", image: "", siteKey: "" });
    });

    it("signs in and goes to the dashboard", async () => {
        vi.spyOn(api, "post").mockResolvedValue({ token: "abc", user: { id: 1, username: "root" } });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(LoginView, router);

        await wrapper.find("#login").setValue("root");
        await wrapper.find("#password").setValue("s3cret-password");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(useAuthStore().isSignedIn).toBe(true);
        expect(push).toHaveBeenCalledWith({ name: "dashboard" });
    });

    it("shows what the api refused", async () => {
        vi.spyOn(api, "post").mockRejectedValue({ message: "The login or the password is incorrect." });

        const wrapper = mountView(LoginView, router);

        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(wrapper.text()).toContain("The login or the password is incorrect.");
    });

    it("draws the challenge the environment declares and sends what was typed", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ provider: "image", token: "signed-token", image: "data:image/png;base64,AAA", siteKey: "" });

        const post = vi.spyOn(api, "post").mockResolvedValue({ token: "abc", user: { id: 1, username: "root" } });
        const wrapper = mountView(LoginView, router);

        await flushPromises();

        expect(wrapper.find("img").attributes("src")).toBe("data:image/png;base64,AAA");

        await wrapper.find("#login").setValue("root");
        await wrapper.find("#password").setValue("s3cret-password");
        await wrapper.find("#captcha").setValue("ab12c");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(post).toHaveBeenCalledWith("/admin/signin", { login: "root", password: "s3cret-password", captchaAnswer: "ab12c", captchaToken: "signed-token" });
    });

    it("draws a new challenge once one was refused", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue({ provider: "image", token: "signed-token", image: "data:image/png;base64,AAA", siteKey: "" });

        vi.spyOn(api, "post").mockRejectedValue({ message: "The challenge was not answered correctly." });

        const wrapper = mountView(LoginView, router);

        await flushPromises();
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        // The challenge and not every call, because the screen also asks the meta for the name it draws.
        expect(get.mock.calls.filter(([path]) => path === "/meta/captcha")).toHaveLength(2);
        expect(wrapper.find("#captcha").element.value).toBe("");
    });

    it("keeps the chosen locale", async () => {
        const wrapper = mountView(LoginView, router);

        await wrapper.find("select").setValue("pt");

        expect(wrapper.text()).toContain("Entrar no admin");
    });
});

describe("DashboardView", () => {
    it("counts what each tile points at", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 7, items: [] });
        usePermissionsStore().reachable = ["tenants", "users", "products", "subscriptions", "plans", "app-events"];

        const meta = useMetaStore();
        meta.environment = "local";
        meta.storageBaseUrl = "/media";

        const wrapper = mountView(DashboardView, createTestRouter());

        await flushPromises();

        expect(wrapper.text()).toContain("7");
        expect(wrapper.text()).toContain("local");
    });

    it("keeps a tile the api could not answer readable", async () => {
        vi.spyOn(api, "get").mockRejectedValue(new Error("offline"));
        usePermissionsStore().reachable = ["tenants"];

        const wrapper = mountView(DashboardView, createTestRouter());

        await flushPromises();

        expect(wrapper.text()).toContain("—");
    });
});

describe("NotFoundView", () => {
    it("offers the way back", async () => {
        const router = createTestRouter();
        const push = vi.spyOn(router, "push");
        const wrapper = mountView(NotFoundView, router);

        expect(wrapper.text()).toContain("This page does not exist.");

        await wrapper.find("main button").trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "dashboard" });
    });
});

describe("ResourceListView", () => {
    let router;

    beforeEach(async () => {
        router = createTestRouter("/tenants");
        await router.isReady();
    });

    it("lists what the api answers", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [TENANT] });

        const wrapper = mountView(ResourceListView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("Acme");
        expect(wrapper.text()).toContain("1 records");
    });

    it("opens the create screen", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 0, items: [] });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("New"))
            .trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-create", params: { resource: "tenants" } });
    });

    it("narrows by search and clears the filters", async () => {
        vi.useFakeTimers();

        const request = vi.spyOn(api, "get").mockResolvedValue({ count: 0, items: [] });
        const wrapper = mountView(ResourceListView, router);

        await vi.advanceTimersByTimeAsync(0);
        await wrapper.find("#filter-search").setValue("acme");
        await vi.advanceTimersByTimeAsync(400);

        expect(request.mock.calls.at(-1)[1]).toMatchObject({ search: "acme" });

        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Clear"))
            .trigger("click");
        await vi.advanceTimersByTimeAsync(400);

        expect(request.mock.calls.at(-1)[1]).toMatchObject({ search: "" });

        vi.useRealTimers();
    });

    it("narrows by a declared filter", async () => {
        const request = vi.spyOn(api, "get").mockResolvedValue({ count: 0, items: [] });
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper.find("#field-active").setValue("true");
        await flushPromises();

        expect(request.mock.calls.at(-1)[1]).toMatchObject({ active: "true" });
    });

    it("sorts and walks the pages", async () => {
        const request = vi.spyOn(api, "get").mockResolvedValue({ count: 60, limit: 25, offset: 0, items: [TENANT] });
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();

        expect(request.mock.calls.at(-1)[1], "opens on the newest primary key").toMatchObject({ ordering: "-id" });

        await wrapper.find("thead button").trigger("click");
        await flushPromises();

        expect(request.mock.calls.at(-1)[1], "clicking the id header flips it").toMatchObject({ ordering: "id" });

        await wrapper.findAll("thead button")[2].trigger("click");
        await flushPromises();

        expect(request.mock.calls.at(-1)[1], "another column sorts by itself").toMatchObject({ ordering: "name" });

        await wrapper.findAll("button").at(-1).trigger("click");
        await flushPromises();

        expect(request.mock.calls.at(-1)[1]).toMatchObject({ offset: 25 });
    });

    it("deletes after the confirmation", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [TENANT] });

        const remove = vi.spyOn(api, "remove").mockResolvedValue(null);
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper.findAll("tbody tr td:last-child button")[2].trigger("click");
        await flushPromises();

        expect(wrapper.text()).toContain("Delete this record?");

        await wrapper.findAll("footer button")[1].trigger("click");
        await flushPromises();

        expect(remove).toHaveBeenCalledWith("/tenants/1");
        expect(useUiStore().toasts.at(-1).tone).toBe("success");
    });

    it("reports a delete the api refused", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [TENANT] });
        vi.spyOn(api, "remove").mockRejectedValue({ message: "This record is referenced by others." });

        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper.findAll("tbody tr td:last-child button")[2].trigger("click");
        await wrapper.findAll("footer button")[1].trigger("click");
        await flushPromises();

        expect(useUiStore().toasts.at(-1).tone).toBe("error");
    });

    it("says on the page that the listing was refused, because an empty grid reads as no records", async () => {
        vi.spyOn(api, "get").mockRejectedValue({ message: "offline" });

        const view = mountView(ResourceListView, router);

        await flushPromises();

        expect(view.text()).toContain("offline");
    });

    it("opens a record for reading and for editing", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [TENANT] });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();

        const actions = wrapper.findAll("tbody tr td:last-child button");

        await actions[0].trigger("click");
        await actions[1].trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-detail", params: { resource: "tenants", id: 1 } });
        expect(push).toHaveBeenCalledWith({ name: "resource-edit", params: { resource: "tenants", id: 1 } });
    });

    it("takes a clicked row to the edit screen of a writable resource", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [TENANT] });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper.find("tbody tr").trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-edit", params: { resource: "tenants", id: 1 } });
    });

    it("takes a clicked row to the read screen of a read only resource", async () => {
        const grants = createTestRouter("/benefit-grants");
        await grants.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ count: 1, limit: 25, offset: 0, items: [{ id: 3, grantKey: "1:activation", status: "completed", grantedQuantity: 1, scheduledAt: "2026-07-29T12:00:00Z" }] });

        const push = vi.spyOn(grants, "push");
        const wrapper = mountView(ResourceListView, grants);

        await flushPromises();
        await wrapper.find("tbody tr").trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-detail", params: { resource: "benefit-grants", id: 3 } });
    });
});

describe("ResourceListView filters", () => {
    it("empties the filters narrowed by the one that moved", async () => {
        const router = createTestRouter("/external-products");
        await router.isReady();

        const request = vi.spyOn(api, "get").mockImplementation((path) =>
            path.includes("/lookup")
                ? Promise.resolve({
                      items: [
                          { id: 7, label: "Monthly" },
                          { id: 8, label: "Yearly" },
                      ],
                  })
                : Promise.resolve({ count: 0, limit: 25, offset: 0, items: [] }),
        );

        const wrapper = mountView(ResourceListView, router);

        await flushPromises();
        await wrapper.find("#field-integrationId").trigger("click");
        await flushPromises();
        await chooseOption(wrapper, 0);
        await flushPromises();
        await wrapper.find("#field-planId").trigger("click");
        await flushPromises();
        await chooseOption(wrapper, 0);
        await flushPromises();

        expect(request.mock.calls.filter((call) => call[0] === "/external-products").at(-1)[1]).toMatchObject({ integrationId: 7, planId: 7 });

        await wrapper.find("#field-integrationId").trigger("click");
        await flushPromises();
        await chooseOption(wrapper, 1);
        await flushPromises();

        expect(request.mock.calls.filter((call) => call[0] === "/external-products").at(-1)[1]).toMatchObject({ integrationId: 8, planId: null });
    });
});

describe("the headings of a screen", () => {
    // A reader walks a page by its headings, so a level skipped is a step that is not there.
    it("go down one level at a time", async () => {
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        useAuthStore().apply("abc", { id: 1, username: "root", timezone: "UTC" });
        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const wrapper = mountView(ResourceFormView, router);
        await flushPromises();

        const levels = [...wrapper.html().matchAll(/<h([1-6])\b/g)].map((found) => Number(found[1]));
        const jumps = levels.slice(1).filter((level, index) => level > levels[index] + 1);

        expect(levels.length).toBeGreaterThan(0);
        expect(jumps).toEqual([]);
    });
});

describe("ResourceFormView", () => {
    it("creates a record with the declared defaults", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        const create = vi.spyOn(api, "post").mockResolvedValue({ id: 5 });
        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("#field-name").setValue("Blue");
        await wrapper.find("#field-domain").setValue("blue.example.org");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(create.mock.calls[0][1]).toMatchObject({ name: "Blue", domain: "blue.example.org", active: true, meta: {} });
        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });

    it("keeps the record the address names when a slower answer arrives after it", async () => {
        // This screen is reused from one record to the next, and saving what an older answer filled in would write it over the record the address names.
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        useAuthStore().apply("abc", { id: 1, username: "root", timezone: "UTC" });

        let settleSlow;
        const slow = new Promise((resolve) => (settleSlow = resolve));

        vi.spyOn(api, "get")
            .mockImplementationOnce(() => slow)
            .mockResolvedValue({ ...TENANT, id: 2, name: "Blue" });

        const wrapper = mountView(ResourceFormView, router);

        await router.push("/tenants/2/edit");
        await flushPromises();

        settleSlow({ ...TENANT, id: 1, name: "Acme" });
        await flushPromises();

        expect(wrapper.find("#field-name").element.value).toBe("Blue");
    });

    it("shows the audit fields of the record it is editing, in the timezone of the account", async () => {
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        useAuthStore().apply("abc", { id: 1, username: "root", timezone: "UTC" });
        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.find("#field-createdAt").text()).toContain("7/29/26");
        expect(wrapper.find("#field-createdAt").attributes("disabled")).toBeDefined();
    });

    it("opens a create screen with the defaults the api would apply", async () => {
        const router = createTestRouter("/content-categories/new");
        await router.isReady();

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.find("[role=switch]").attributes("aria-checked")).toBe("true");
    });

    it("empties every level below the one that moved", async () => {
        const router = createTestRouter("/external-products/new");
        await router.isReady();

        vi.spyOn(api, "get").mockImplementation((path) => {
            if (path === "/plans/lookup/3") {
                return Promise.resolve({ id: 3, label: "Monthly" });
            }

            return Promise.resolve(path.startsWith("/integrations/lookup") ? { items: [{ id: 7, label: "acme - stripe" }] } : { items: [{ id: 3, label: "Monthly" }] });
        });

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("#field-integrationId").trigger("click");
        await flushPromises();
        await chooseOption(wrapper, 0);
        await flushPromises();
        await wrapper.find("#field-planId").trigger("click");
        await flushPromises();
        await chooseOption(wrapper, 0);
        await flushPromises();

        expect(wrapper.find("#field-planId").text()).toContain("Monthly");

        await wrapper.findAll("#field-integrationId svg")[0].trigger("click");
        await flushPromises();

        expect(wrapper.find("#field-planId").text()).toContain("Choose Integration first");
        expect(wrapper.find("#field-planId").attributes("disabled")).toBeDefined();
    });

    it("keeps the audit fields out of the create screen", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.find("#field-createdAt").exists()).toBe(false);
    });

    it("never sends a read only field back", async () => {
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const update = vi.spyOn(api, "put").mockResolvedValue({ id: 1 });
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(update.mock.calls[0][1]).not.toHaveProperty("createdAt");
        expect(update.mock.calls[0][1]).not.toHaveProperty("updatedAt");
    });

    it("loads a record for editing and updates it", async () => {
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const update = vi.spyOn(api, "put").mockResolvedValue({ id: 1 });
        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.find("#field-name").element.value).toBe("Acme");

        await wrapper.find("#field-name").setValue("Acme Books");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(update.mock.calls[0][0]).toBe("/tenants/1");
        expect(update.mock.calls[0][1]).toMatchObject({ name: "Acme Books" });
        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });

    it("leaves an untouched password out of the payload", async () => {
        const router = createTestRouter("/users/1/edit");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, username: "root", email: "root@acme.com", role: "administrator", status: "active", gender: "none", timezone: "UTC", meta: {} });

        const update = vi.spyOn(api, "put").mockResolvedValue({ id: 1 });
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(update.mock.calls[0][1]).not.toHaveProperty("password");
    });

    it("shows the field errors the api answered", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        vi.spyOn(api, "post").mockRejectedValue({ errors: { domain: "This domain is already in use." }, message: "" });

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(wrapper.text()).toContain("This domain is already in use.");
    });

    it("shows a failure that names no field", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        vi.spyOn(api, "post").mockRejectedValue({ errors: {}, message: "Something went wrong." });

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(wrapper.text()).toContain("Something went wrong.");
    });

    it("reports a record it could not load", async () => {
        const router = createTestRouter("/tenants/9/edit");
        await router.isReady();

        vi.spyOn(api, "get").mockRejectedValue({ message: "The requested record was not found." });

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("The requested record was not found.");
    });

    it("keeps editing a record it just created", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        vi.spyOn(api, "post").mockResolvedValue({ id: 5 });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("continue"))
            .trigger("click");
        await flushPromises();

        expect(push).toHaveBeenCalledWith({ name: "resource-edit", params: { resource: "tenants", id: 5 } });
    });

    it("stays on the record it is editing and refreshes what the api derived", async () => {
        const router = createTestRouter("/tenants/1/edit");
        await router.isReady();

        const read = vi.spyOn(api, "get").mockResolvedValue(TENANT);
        vi.spyOn(api, "put").mockResolvedValue({ ...TENANT, name: "Acme Books" });

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("continue"))
            .trigger("click");
        await flushPromises();

        expect(push).not.toHaveBeenCalled();
        expect(read).toHaveBeenCalledTimes(2);
        expect(useUiStore().toasts.at(-1).tone).toBe("success");
    });

    it("offers to keep editing only where the record may be edited", async () => {
        const editable = createTestRouter("/tenants/new");
        await editable.isReady();

        const withEdit = mountView(ResourceFormView, editable);
        await flushPromises();

        expect(withEdit.findAll("button").some((button) => button.text().includes("continue"))).toBe(true);

        const ledger = createTestRouter("/credit-transactions/new");
        await ledger.isReady();

        const withoutEdit = mountView(ResourceFormView, ledger);
        await flushPromises();

        expect(withoutEdit.findAll("button").some((button) => button.text().includes("continue"))).toBe(false);
    });

    it("goes to the grid when the create is cancelled", async () => {
        const router = createTestRouter("/tenants/new");
        await router.isReady();

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Cancel"))
            .trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });

    it("goes to the grid when the edit is cancelled, whatever screen led here", async () => {
        const router = createTestRouter("/tenants/1");
        await router.isReady();
        await router.push("/tenants/1/edit");

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Cancel"))
            .trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });
});

describe("ResourceDetailView", () => {
    it("says a secret is kept under the field that never shows it", async () => {
        const router = createTestRouter("/integrations/1/edit");
        await router.isReady();

        const meta = useMetaStore();
        meta.providerCredentials = { revenuecat: [{ field: "revenuecat_api_key", label: "Secret API key (v1)", hint: "Project settings" }] };
        meta.enums = { provider: ["revenuecat"], environment: ["sandbox", "production"] };

        const record = { id: 1, tenantId: 1, provider: "revenuecat", environment: "sandbox", hasRevenuecatApiKey: true, active: true, meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" };

        vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve(path.includes("/lookup") ? { items: [] } : record));

        const wrapper = mountView(ResourceFormView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("A value is already stored");
    });

    it("reads a gateway group as whether each key is kept", async () => {
        const router = createTestRouter("/integrations/1");
        await router.isReady();

        const meta = useMetaStore();
        meta.providerCredentials = { revenuecat: [{ field: "secret", label: "Secret API key (v1)", hint: "Project settings" }] };

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, tenantId: 1, provider: "revenuecat", environment: "sandbox", webhookKey: "abc", hasRevenuecatApiKey: true, active: true, meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("Secret API key (v1)");
    });

    it("reads a record and groups its fields", async () => {
        const router = createTestRouter("/tenants/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("Acme");
        expect(wrapper.text()).toContain("Identification");
        expect(wrapper.text()).toContain("Audit");
    });

    it("shows the expanded relation of a lookup", async () => {
        const router = createTestRouter("/users/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, username: "root", role: "administrator", status: "active", gender: "none", timezone: "UTC", meta: {}, tenantId: 1, tenant: { id: 1, code: "acme", name: "Acme" }, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("Acme");
    });

    it("shows the raw id when the relation is empty", async () => {
        const router = createTestRouter("/users/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, username: "root", role: "administrator", status: "active", gender: "none", timezone: "UTC", meta: {}, tenantId: null, tenant: null, languageId: 4, language: null, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("4");
    });

    it("hides the password of a record", async () => {
        const router = createTestRouter("/users/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, username: "root", role: "administrator", status: "active", gender: "none", timezone: "UTC", meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).not.toContain("Password");
    });

    it("opens the edit screen and goes back to the list", async () => {
        const router = createTestRouter("/tenants/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Edit"))
            .trigger("click");
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Back"))
            .trigger("click");

        expect(push).toHaveBeenCalledWith({ name: "resource-edit", params: { resource: "tenants", id: 1 } });
        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });

    it("deletes after the confirmation", async () => {
        const router = createTestRouter("/tenants/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);

        const remove = vi.spyOn(api, "remove").mockResolvedValue(null);
        const push = vi.spyOn(router, "push");
        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Delete"))
            .trigger("click");
        await flushPromises();
        await wrapper.findAll("footer button")[1].trigger("click");
        await flushPromises();

        expect(remove).toHaveBeenCalledWith("/tenants/1");
        expect(push).toHaveBeenCalledWith({ name: "resource-list", params: { resource: "tenants" } });
    });

    it("reports a delete the api refused", async () => {
        const router = createTestRouter("/tenants/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue(TENANT);
        vi.spyOn(api, "remove").mockRejectedValue({ message: "This record is referenced by others." });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Delete"))
            .trigger("click");
        await wrapper.findAll("footer button")[1].trigger("click");
        await flushPromises();

        expect(useUiStore().toasts.at(-1).tone).toBe("error");
    });

    it("activates a subscription and reports what was delivered", async () => {
        const router = createTestRouter("/subscriptions/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, tenantId: 1, userId: 1, planId: 1, status: "active", benefitStatus: "active", cancelAtPeriodEnd: false, meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });

        const activate = vi.spyOn(api, "post").mockResolvedValue({ granted: 2 });
        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Activate"))
            .trigger("click");
        await flushPromises();

        expect(activate).toHaveBeenCalledWith("/subscriptions/1/activate");
        expect(useUiStore().toasts.at(-1).message).toBe("2 deliveries were made.");
    });

    it("reports an activation the api refused", async () => {
        const router = createTestRouter("/subscriptions/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({ id: 1, tenantId: 1, userId: 1, planId: 1, status: "active", benefitStatus: "active", cancelAtPeriodEnd: false, meta: {}, createdAt: "2026-07-29T12:00:00Z", updatedAt: "2026-07-29T12:00:00Z" });
        vi.spyOn(api, "post").mockRejectedValue({ message: "offline" });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();
        await wrapper
            .findAll("button")
            .find((button) => button.text().includes("Activate"))
            .trigger("click");
        await flushPromises();

        expect(useUiStore().toasts.at(-1).tone).toBe("error");
    });

    it("reports a record it could not read", async () => {
        const router = createTestRouter("/tenants/9");
        await router.isReady();

        vi.spyOn(api, "get").mockRejectedValue({ message: "The requested record was not found." });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.text()).toContain("The requested record was not found.");
    });

    it("hides the write actions of a read only resource", async () => {
        const router = createTestRouter("/benefit-grants/1");
        await router.isReady();

        vi.spyOn(api, "get").mockResolvedValue({
            id: 1,
            subscription_benefit_id: 1,
            grantKey: "1:activation",
            cycleKey: "activation",
            scheduledAt: "2026-07-29T12:00:00Z",
            status: "completed",
            requestedQuantity: 1,
            grantedQuantity: 1,
            result: {},
            attempts: 1,
            meta: {},
            createdAt: "2026-07-29T12:00:00Z",
            updatedAt: "2026-07-29T12:00:00Z",
        });

        const wrapper = mountView(ResourceDetailView, router);

        await flushPromises();

        expect(wrapper.findAll("button").some((button) => button.text().includes("Delete"))).toBe(false);
        expect(wrapper.findAll("button").some((button) => button.text().includes("Edit"))).toBe(false);
    });
});

describe("App", () => {
    it("hosts the routed view and the toasts", async () => {
        const router = createTestRouter();
        await router.isReady();

        const wrapper = mount(App, { global: { plugins: [router], stubs: { RouterView: true } } });

        expect(wrapper.html()).toContain("router-view");
    });
});
