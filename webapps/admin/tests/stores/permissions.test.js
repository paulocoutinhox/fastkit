import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { usePermissionsStore } from "@/stores/permissions";

describe("permissions", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it("asks the api what this account reaches", async () => {
        const request = vi.spyOn(api, "get").mockResolvedValue({ resources: ["contents", "galleries"] });
        const permissions = usePermissionsStore();

        await permissions.load();

        expect(request).toHaveBeenCalledWith("/meta/permissions");
        expect(permissions.reaches("contents")).toBe(true);
        expect(permissions.reaches("plans")).toBe(false);
    });

    it("asks once and answers from what it was told", async () => {
        const request = vi.spyOn(api, "get").mockResolvedValue({ resources: [] });
        const permissions = usePermissionsStore();

        await permissions.load();
        await permissions.load();

        expect(request).toHaveBeenCalledTimes(1);
    });

    it("forgets what the account before this one reached", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ resources: ["contents"] });
        const permissions = usePermissionsStore();

        await permissions.load();
        useAuthStore().apply("another", { id: 2, username: "editor" });

        expect(permissions.loaded).toBe(false);
        expect(permissions.reaches("contents")).toBe(false);
    });

    it("keeps whether the account belongs to a brand, which is what stops a form offering one option", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ resources: ["contents"], confined: true });
        const permissions = usePermissionsStore();

        await permissions.load();

        expect(permissions.confined).toBe(true);
    });

    it("forgets that too when another account signs in", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ resources: ["contents"], confined: true });
        const permissions = usePermissionsStore();

        await permissions.load();
        useAuthStore().apply("another", { id: 2, username: "editor" });

        expect(permissions.confined).toBe(false);
    });
});
