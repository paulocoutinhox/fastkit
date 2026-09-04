import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory } from "vue-router";

import { META, answering } from "../helpers/api";
import { api } from "@/api/client";
import { createAppRouter } from "@/router";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { flushPromises } from "@vue/test-utils";

function build() {
    return createAppRouter(createMemoryHistory());
}

describe("what a role reaches", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        useAuthStore().apply("abc", { id: 1, username: "editor" });
    });

    it("opens a resource the account reaches", async () => {
        answering(["contents"]);

        const router = build();
        await router.push("/contents");

        expect(router.currentRoute.value.name).toBe("resource-list");
    });

    it("refuses the address of a resource the account does not reach", async () => {
        answering(["contents"]);

        const router = build();
        await router.push("/plans");

        expect(router.currentRoute.value.name).toBe("dashboard");
    });

    it("refuses every screen of it and not only the list", async () => {
        answering(["contents"]);

        const router = build();

        for (const path of ["/plans/new", "/plans/1", "/plans/1/edit"]) {
            await router.push(path);

            expect(router.currentRoute.value.name, path).toBe("dashboard");
        }
    });

    it("shows the boot screen while it is finding out, and never a menu it would take away", async () => {
        const held = [];
        vi.spyOn(api, "get").mockImplementation((path) => new Promise((resolve) => held.push(() => resolve(path === "/meta/permissions" ? { resources: ["contents"] } : META))));

        const ui = useUiStore();
        const router = build();
        const walking = router.push("/contents");

        await flushPromises();

        expect(ui.booting).toBe(true);

        held.forEach((release) => release());
        await walking;

        expect(ui.booting).toBe(false);
        expect(router.currentRoute.value.name).toBe("resource-list");
    });

    it("keeps the boot screen and says what stopped it when it cannot find out at all", async () => {
        vi.spyOn(api, "get").mockRejectedValue(new Error("the server is not answering"));

        const ui = useUiStore();
        const router = build();

        await router.push("/contents").catch(() => null);

        expect(ui.booting).toBe(true);
        expect(ui.bootFailure).toBe("the server is not answering");
    });

    it("finds out once, and does not blink on every screen after it", async () => {
        answering(["contents"]);

        const ui = useUiStore();
        const router = build();

        await router.push("/contents");

        const seen = [];
        router.beforeEach(() => {
            seen.push(ui.booting);
        });

        await router.push("/contents/1");

        expect(seen).toEqual([false]);
    });
});
