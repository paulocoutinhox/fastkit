import { describe, expect, it, vi } from "vitest";

import { api } from "@/api/client";
import { LOCALE_STORAGE_KEY } from "@/i18n";
import { TOKEN_STORAGE_KEY, useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { TOAST_TIMEOUT, useUiStore } from "@/stores/ui";

describe("auth store", () => {
    it("starts signed out", () => {
        const auth = useAuthStore();

        expect(auth.isSignedIn).toBe(false);
        expect(auth.timezone).toBe("UTC");
    });

    it("keeps the session after signing in", async () => {
        vi.spyOn(api, "post").mockResolvedValue({ token: "abc", user: { id: 1, username: "root", timezone: "America/Sao_Paulo" } });

        const auth = useAuthStore();
        await auth.signIn("root", "s3cret-password");

        expect(auth.isSignedIn).toBe(true);
        expect(auth.timezone).toBe("America/Sao_Paulo");
        expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("abc");
    });

    it("discards an account refresh that arrives after signing out", async () => {
        let answer;
        vi.spyOn(api, "get").mockImplementation(
            () =>
                new Promise((resolve) => {
                    answer = resolve;
                }),
        );

        const auth = useAuthStore();
        auth.apply("session", { id: 1 });
        const pending = auth.refresh();
        auth.signOut();
        answer({ id: 1, username: "former-account" });

        expect(await pending).toBeNull();
        expect(auth.user).toBeNull();
        expect(auth.isSignedIn).toBe(false);
    });

    it("discards a refresh after the same token opens another session", async () => {
        const response = Promise.withResolvers();
        vi.spyOn(api, "get").mockReturnValue(response.promise);

        const auth = useAuthStore();
        auth.apply("same-token", { id: 1, firstName: "Earlier" });

        const pending = auth.refresh();

        auth.signOut();
        auth.apply("same-token", { id: 1, firstName: "Current" });
        response.resolve({ id: 1, firstName: "Earlier" });

        expect(await pending).toBeNull();
        expect(auth.user.firstName).toBe("Current");
    });

    it("does not restore a session when sign in completes after signing out", async () => {
        const response = Promise.withResolvers();
        vi.spyOn(api, "post").mockReturnValue(response.promise);

        const auth = useAuthStore();
        const pending = auth.signIn("root", "s3cret-password");

        auth.signOut();
        response.resolve({ token: "earlier-session", user: { id: 1 } });

        await pending;

        expect(auth.isSignedIn).toBe(false);
        expect(auth.user).toBeNull();
    });

    it("clears the session on signing out", () => {
        const auth = useAuthStore();

        auth.apply("abc", { id: 1, username: "root" });
        auth.signOut();

        expect(auth.isSignedIn).toBe(false);
        expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    });

    it("keeps what is not the session, so signing out never costs the chosen language", () => {
        const auth = useAuthStore();

        localStorage.setItem(LOCALE_STORAGE_KEY, "pt");
        auth.apply("abc", { id: 1, username: "root" });
        auth.signOut();

        expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("pt");
    });
});

describe("ui store", () => {
    it("stacks and dismisses toasts", () => {
        vi.useFakeTimers();

        const ui = useUiStore();

        ui.success("saved");
        ui.error("broken");
        ui.info("notice");

        expect(ui.toasts).toHaveLength(3);
        expect(ui.toasts[0].tone).toBe("success");

        ui.dismiss(ui.toasts[0].id);

        expect(ui.toasts).toHaveLength(2);

        vi.advanceTimersByTime(TOAST_TIMEOUT);

        expect(ui.toasts).toHaveLength(0);

        vi.useRealTimers();
    });

    it("toggles the sidebar", () => {
        const ui = useUiStore();

        ui.toggleSidebar();
        expect(ui.sidebarOpen).toBe(true);

        ui.toggleSidebar();
        expect(ui.sidebarOpen).toBe(false);

        ui.toggleSidebar(true);
        expect(ui.sidebarOpen).toBe(true);
    });
});

describe("meta store", () => {
    it("loads once and answers the enum options", async () => {
        const payload = { environment: "local", version: "1.0.0", storageBaseUrl: "/media", enums: { user_role: ["normal", "administrator"] }, timezones: ["UTC"] };
        const request = vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve(path === "/meta" ? payload : [{ id: 2, codeIso6391: "pt" }]));

        const meta = useMetaStore();

        await meta.load();
        await meta.load();

        expect(request.mock.calls.map(([path]) => path)).toEqual(["/meta", "/languages/active"]);
        expect(meta.languages).toEqual([{ id: 2, codeIso6391: "pt" }]);
        expect(meta.environment).toBe("local");
        expect(meta.version).toBe("1.0.0");
        expect(meta.options("user_role")).toEqual(["normal", "administrator"]);
        expect(meta.options("unknown")).toEqual([]);
    });
});
