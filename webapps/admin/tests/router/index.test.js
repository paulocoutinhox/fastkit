import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory } from "vue-router";

import { answering } from "../helpers/api";
import { api } from "@/api/client";
import { createAppRouter } from "@/router";
import { useAuthStore } from "@/stores/auth";

function build() {
    return createAppRouter(createMemoryHistory());
}

describe("router", () => {
    it("sends an anonymous visitor to the login", async () => {
        const router = build();

        await router.push("/users");
        await router.isReady();

        expect(router.currentRoute.value.name).toBe("login");
    });

    it("keeps an anonymous visitor on the login", async () => {
        const router = build();

        await router.push("/login");
        await router.isReady();

        expect(router.currentRoute.value.name).toBe("login");
    });

    it("sends a signed in administrator away from the login", async () => {
        answering(["users", "app-events"]);

        const router = build();
        useAuthStore().apply("abc", { id: 1, username: "root" });

        await router.push("/login");
        await router.isReady();

        expect(router.currentRoute.value.name).toBe("dashboard");
    });

    it("loads what the admin needs before a protected screen", async () => {
        const request = answering(["users"]);

        const router = build();
        useAuthStore().apply("abc", { id: 1, username: "root" });

        await router.push("/users");
        await router.isReady();

        expect(router.currentRoute.value.name).toBe("resource-list");
        expect(request).toHaveBeenCalledWith("/meta");
        expect(request).toHaveBeenCalledWith("/meta/permissions");
    });

    it("routes every screen of a resource", async () => {
        answering(["users", "app-events"]);

        const router = build();
        useAuthStore().apply("abc", { id: 1, username: "root" });

        await router.push("/users/new");
        expect(router.currentRoute.value.name).toBe("resource-create");

        await router.push("/users/1");
        expect(router.currentRoute.value.name).toBe("resource-detail");

        await router.push("/users/1/edit");
        expect(router.currentRoute.value.name).toBe("resource-edit");
    });

    it("refuses the form of a resource the api never lets anyone write", async () => {
        answering(["users", "app-events"]);

        const router = build();
        useAuthStore().apply("abc", { id: 1, username: "root" });

        await router.push("/app-events/new");
        expect(router.currentRoute.value.name).toBe("resource-list");

        await router.push("/app-events/1/edit");
        expect(router.currentRoute.value.name).toBe("resource-list");

        await router.push("/app-events/1");
        expect(router.currentRoute.value.name).toBe("resource-detail");
    });

    it("draws the not found screen for an address no resource answers", async () => {
        answering(["users"]);

        const router = build();
        useAuthStore().apply("abc", { id: 1, username: "root" });

        await router.push("/nothing-here");
        expect(router.currentRoute.value.name).toBe("not-found");

        await router.push("/nothing-here/1/edit");
        expect(router.currentRoute.value.name).toBe("not-found");
    });

    it("scrolls a new screen to the top", () => {
        expect(build().options.scrollBehavior()).toEqual({ top: 0 });
    });
});
