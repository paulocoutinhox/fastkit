import { describe, expect, it } from "vitest";

import { i18n } from "../setup";
import App from "@/App.vue";
import AppBoot from "@/components/layout/AppBoot.vue";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";
import { flushPromises, mount } from "@vue/test-utils";

describe("AppBoot", () => {
    it("says what is happening while the panel is being put together", () => {
        useMetaStore().name = "Acme Panel";

        const wrapper = mount(AppBoot, { global: { plugins: [i18n] } });

        expect(wrapper.text()).toContain("Acme Panel");
        expect(wrapper.text()).toContain("Loading");
        expect(wrapper.find('[role="status"]').exists()).toBe(true);
    });

    it("is what the panel shows instead of a menu it would have to take away", () => {
        const ui = useUiStore();
        ui.booting = true;

        const wrapper = mount(App, { global: { plugins: [i18n], stubs: { RouterView: { template: "<div id='screen' />" }, ToastStack: true } } });

        expect(wrapper.findComponent(AppBoot).exists()).toBe(true);
        expect(wrapper.find("#screen").exists()).toBe(false);
    });

    it("steps aside once there is something to draw", () => {
        const wrapper = mount(App, { global: { plugins: [i18n], stubs: { RouterView: { template: "<div id='screen' />" }, ToastStack: true } } });

        expect(wrapper.findComponent(AppBoot).exists()).toBe(false);
        expect(wrapper.find("#screen").exists()).toBe(true);
    });
});

describe("DashboardView tiles", () => {
    it("counts what the account reaches, and never a card that would answer 403", async () => {
        const { default: DashboardView } = await import("@/views/DashboardView.vue");
        const { usePermissionsStore } = await import("@/stores/permissions");
        const { createTestRouter } = await import("../helpers/router");
        const { api } = await import("@/api/client");
        const { vi } = await import("vitest");

        vi.spyOn(api, "get").mockResolvedValue({ count: 3, items: [] });
        usePermissionsStore().reachable = ["contents", "galleries", "banners", "content-categories"];

        const router = createTestRouter();
        await router.isReady();

        const wrapper = mount(DashboardView, { global: { plugins: [i18n, router] } });
        await flushPromises();

        const links = wrapper.findAll(".grid a");

        expect(links.length).toBe(4);
        expect(wrapper.text()).toContain("Contents");
        expect(links.map((link) => link.text())).not.toContain(expect.stringContaining("Tenants"));
    });
});
