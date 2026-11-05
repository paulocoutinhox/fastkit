import { describe, expect, it, vi } from "vitest";

import { answering } from "../helpers/api";
import { createTestRouter } from "../helpers/router";
import { api } from "@/api/client";
import EmailCodeLogin from "@/components/auth/EmailCodeLogin.vue";
import SignInChallenge from "@/components/auth/SignInChallenge.vue";
import SocialConnections from "@/components/auth/SocialConnections.vue";
import SocialSignInButtons from "@/components/auth/SocialSignInButtons.vue";
import { TOKEN_STORAGE_KEY, useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { AuthenticationHelper } from "@/support/authentication-helper";
import LoginView from "@/views/LoginView.vue";
import { flushPromises, mount } from "@vue/test-utils";

const DISABLED = { provider: "disabled", token: "", image: "", siteKey: "" };
const CHALLENGE = { challenge: "opaque-challenge", expiresAt: "2026-11-05T20:00:00Z", resendAt: "2026-11-05T19:51:00Z" };
const SESSION = { token: "application-session", user: { token: "account-id", email: "operator@example.com", hasPassword: false } };

async function requestCode(wrapper) {
    await flushPromises();
    await wrapper.find("#sign-in-email").setValue("operator@example.com");
    await wrapper.find("form").trigger("submit");
    await flushPromises();
}

describe("email code sign-in", () => {
    it("requests a code and opens the operator session only after confirmation", async () => {
        vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        const post = vi.spyOn(api, "post").mockImplementation((path) => Promise.resolve(path === "/auth/email/request" ? CHALLENGE : SESSION));
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);

        expect(post).toHaveBeenCalledWith("/auth/email/request", { email: "operator@example.com", surface: "admin", captchaAnswer: "", captchaToken: "" });
        expect(useAuthStore().isSignedIn).toBe(false);
        expect(wrapper.text()).toContain("operator@example.com");

        await wrapper.find("#sign-in-code").setValue("123456");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(post).toHaveBeenLastCalledWith("/auth/email/confirm", { challenge: CHALLENGE.challenge, code: "123456", surface: "admin" });
        expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe(SESSION.token);
        expect(wrapper.emitted("signed-in")).toHaveLength(1);
    });

    it("allows another request without keeping the old code", async () => {
        vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        vi.spyOn(api, "post").mockResolvedValue(CHALLENGE);
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);
        await wrapper.find("#sign-in-code").setValue("123456");
        await wrapper.findAll("button").at(-1).trigger("click");
        await flushPromises();

        expect(wrapper.find("#sign-in-code").exists()).toBe(false);
        expect(wrapper.find("#sign-in-email").element.value).toBe("operator@example.com");
    });

    it("shows a refused code without signing in", async () => {
        vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        vi.spyOn(api, "post").mockResolvedValueOnce(CHALLENGE).mockRejectedValueOnce({ message: "The code expired." });
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);
        await wrapper.find("#sign-in-code").setValue("123456");
        await wrapper.find("form").trigger("submit");
        await flushPromises();

        expect(wrapper.text()).toContain("The code expired.");
        expect(useAuthStore().isSignedIn).toBe(false);
    });

    it("redraws verification when requesting a code fails", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        vi.spyOn(api, "post").mockRejectedValue({ message: "Wait before requesting another code." });
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);

        expect(wrapper.text()).toContain("Wait before requesting another code.");
        expect(get).toHaveBeenCalledTimes(2);
    });

    it("ignores a code request that arrives after the session changes", async () => {
        vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        const pending = Promise.withResolvers();
        vi.spyOn(api, "post").mockReturnValue(pending.promise);
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);
        useAuthStore().apply("another-session", { token: "another-account" });
        pending.resolve(CHALLENGE);
        await flushPromises();

        expect(wrapper.find("#sign-in-code").exists()).toBe(false);
        expect(useAuthStore().token).toBe("another-session");
    });

    it("discards a confirmed code that arrives after signing out", async () => {
        vi.spyOn(api, "get").mockResolvedValue(DISABLED);
        const pending = Promise.withResolvers();
        vi.spyOn(api, "post").mockResolvedValueOnce(CHALLENGE).mockReturnValueOnce(pending.promise);
        const wrapper = mount(EmailCodeLogin);

        await requestCode(wrapper);
        await wrapper.find("#sign-in-code").setValue("123456");
        await wrapper.find("form").trigger("submit");
        useAuthStore().signOut();
        pending.resolve(SESSION);
        await flushPromises();

        expect(useAuthStore().isSignedIn).toBe(false);
        expect(wrapper.emitted("signed-in")).toBeUndefined();
    });
});

describe("sign-in verification", () => {
    it("waits for the challenge before it can be solved", async () => {
        vi.spyOn(api, "get").mockReturnValue(new Promise(() => {}));
        const wrapper = mount(SignInChallenge);

        await expect(wrapper.vm.solve()).rejects.toThrow("Wait for the verification");
        expect(wrapper.vm.ready).toBe(false);
    });

    it("reads an image answer and clears it when the challenge is replaced", async () => {
        vi.spyOn(api, "get").mockResolvedValue({ provider: "image", token: "image-proof", image: "data:image/png;base64,AA", siteKey: "" });
        const wrapper = mount(SignInChallenge);
        await flushPromises();
        await wrapper.find("#captcha").setValue("abc123");

        expect(await wrapper.vm.solve()).toEqual({ captchaAnswer: "abc123", captchaToken: "image-proof" });

        await wrapper.vm.reset();
        expect(wrapper.find("#captcha").element.value).toBe("");
    });
});

describe("social sign-in", () => {
    it("offers no provider buttons until a provider is enabled", () => {
        const wrapper = mount(SocialSignInButtons);

        expect(wrapper.find("a").exists()).toBe(false);
    });

    it("starts the server flow and carries the intended panel page", () => {
        useMetaStore().authentication = { emailCode: false, social: [{ provider: "google", label: "Google" }] };
        const wrapper = mount(SocialSignInButtons, { props: { next: "/users/5/edit" } });
        const address = new URL(wrapper.find("a").attributes("href"), "https://local.example");

        expect(address.pathname).toBe("/account/social/google/start");
        expect(address.searchParams.get("surface")).toBe("admin");
        expect(address.searchParams.get("next")).toBe("/users/5/edit");
        expect(wrapper.text()).toContain("Continue with Google");
    });

    it("removes the callback fragment before redeeming the admin ticket", async () => {
        answering([], { "/meta/captcha": DISABLED });
        const post = vi.spyOn(api, "post").mockResolvedValue(SESSION);
        const router = createTestRouter("/login?next=/profile#sign-in=opaque-ticket");
        await router.isReady();
        const replace = vi.spyOn(router, "replace");

        mount(LoginView, { global: { plugins: [router] } });
        await flushPromises();

        expect(replace).toHaveBeenCalledWith({ path: "/login", query: { next: "/profile" }, hash: "" });
        expect(post).toHaveBeenCalledWith("/admin/social/redeem", { ticket: "opaque-ticket" });
        expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe(SESSION.token);
        expect(router.currentRoute.value.path).toBe("/profile");
        expect(router.currentRoute.value.hash).toBe("");
    });

    it("explains why an existing account must connect the provider first", async () => {
        answering([], { "/meta/captcha": DISABLED });
        const router = createTestRouter("/login#sign-in-error=error.social-link-required");
        await router.isReady();
        const wrapper = mount(LoginView, { global: { plugins: [router] } });
        await flushPromises();

        expect(wrapper.text()).toContain("Sign in with your existing method");
        expect(useAuthStore().isSignedIn).toBe(false);
        expect(router.currentRoute.value.hash).toBe("");
    });

    it("treats an unknown callback error as an invalid response", () => {
        expect(AuthenticationHelper.socialError("__proto__")).toBe("auth.socialInvalidResponse");
    });
});

describe("social connections", () => {
    const GOOGLE = { provider: "google", label: "Google", enabled: true, connected: false, createdAt: null };

    it("opens the provider only after the server prepares the authenticated connection", async () => {
        vi.spyOn(api, "get").mockResolvedValue([GOOGLE]);
        const post = vi.spyOn(api, "post").mockResolvedValue({ authorizationUrl: "https://accounts.google.com/authorize" });
        const navigate = vi.spyOn(AuthenticationHelper, "navigate").mockImplementation(() => {});
        const wrapper = mount(SocialConnections);
        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(post).toHaveBeenCalledWith("/account/social-connections/google/start", { surface: "admin" });
        expect(navigate).toHaveBeenCalledWith("https://accounts.google.com/authorize");
    });

    it("refreshes the connection after it is removed", async () => {
        vi.spyOn(api, "get")
            .mockResolvedValueOnce([{ ...GOOGLE, connected: true }])
            .mockResolvedValueOnce([GOOGLE]);
        const remove = vi.spyOn(api, "remove").mockResolvedValue(null);
        const wrapper = mount(SocialConnections);
        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(remove).toHaveBeenCalledWith("/account/social-connections/google?surface=admin");
        expect(wrapper.text()).toContain("Social account disconnected.");
        expect(wrapper.find("button").text()).toBe("Connect");
    });

    it("keeps the connection when removing the last method is refused", async () => {
        vi.spyOn(api, "get").mockResolvedValue([{ ...GOOGLE, connected: true }]);
        vi.spyOn(api, "remove").mockRejectedValue({ message: "Add another sign-in method first." });
        const wrapper = mount(SocialConnections);
        await flushPromises();
        await wrapper.find("button").trigger("click");
        await flushPromises();

        expect(wrapper.text()).toContain("Add another sign-in method first.");
        expect(wrapper.find("button").text()).toBe("Disconnect");
    });

    it("does not navigate when another session opens during connection preparation", async () => {
        vi.spyOn(api, "get").mockResolvedValue([GOOGLE]);
        const pending = Promise.withResolvers();
        vi.spyOn(api, "post").mockReturnValue(pending.promise);
        const navigate = vi.spyOn(AuthenticationHelper, "navigate").mockImplementation(() => {});
        const wrapper = mount(SocialConnections);
        await flushPromises();
        await wrapper.find("button").trigger("click");

        useAuthStore().apply("another-session", { token: "another-account" });
        pending.resolve({ authorizationUrl: "https://accounts.google.com/authorize" });
        await flushPromises();

        expect(navigate).not.toHaveBeenCalled();
    });
});
