import { beforeEach, describe, expect, it, vi } from "vitest";

import { i18n } from "../setup";
import { ApiError } from "@/api/api-error";
import { api, configure } from "@/api/client";

function respondWith(status, payload) {
    return vi.fn().mockResolvedValue({ status, ok: status < 400, json: () => Promise.resolve(payload) });
}

describe("api client", () => {
    beforeEach(() => {
        configure({ token: null, locale: "en", onUnauthorized: null });
    });

    it("prefixes every path with the api root", async () => {
        global.fetch = respondWith(200, { items: [] });

        await api.get("/users");

        expect(global.fetch).toHaveBeenCalledWith("/api/users", expect.objectContaining({ method: "GET" }));
    });

    it("drops empty query parameters", async () => {
        global.fetch = respondWith(200, {});

        await api.get("/users", { search: "ada", ordering: "", limit: 10, offset: null });

        expect(global.fetch.mock.calls[0][0]).toBe("/api/users?search=ada&limit=10");
    });

    it("carries the token and the locale", async () => {
        global.fetch = respondWith(200, {});
        configure({ token: "abc", locale: "pt" });

        await api.get("/users");

        expect(global.fetch.mock.calls[0][1].headers).toEqual({ Authorization: "Bearer abc", "Accept-Language": "pt" });
    });

    it("sends a json body on a write", async () => {
        global.fetch = respondWith(200, {});

        await api.post("/users", { username: "ada" });

        const [, options] = global.fetch.mock.calls[0];

        expect(options.headers["Content-Type"]).toBe("application/json");
        expect(options.body).toBe('{"username":"ada"}');
    });

    it("updates through put", async () => {
        global.fetch = respondWith(200, { id: 1 });

        expect(await api.put("/users/1", { username: "ada" })).toEqual({ id: 1 });
        expect(global.fetch.mock.calls[0][1].method).toBe("PUT");
    });

    it("answers nothing on a no content response", async () => {
        global.fetch = vi.fn().mockResolvedValue({ status: 204, ok: true });

        expect(await api.remove("/users/1")).toBeNull();
    });

    it("sends a file as multipart without forcing the content type", async () => {
        global.fetch = respondWith(201, { key: "images/one.png" });

        await api.upload("image", new File(["x"], "one.png"));

        const [url, options] = global.fetch.mock.calls[0];

        expect(url).toBe("/api/uploads/image");
        expect(options.body).toBeInstanceOf(FormData);
        expect(options.headers["Content-Type"]).toBeUndefined();
    });

    it("raises a typed error carrying the field messages", async () => {
        global.fetch = respondWith(422, { code: "error.validation", detail: "Check the fields.", errors: { name: "Required" } });

        await expect(api.post("/users", {})).rejects.toMatchObject({ status: 422, code: "error.validation", errors: { name: "Required" } });
    });

    it("reports an unreadable error response as a typed error", async () => {
        global.fetch = vi.fn().mockResolvedValue({ status: 500, ok: false, json: () => Promise.reject(new Error("no body")) });

        await expect(api.get("/users")).rejects.toBeInstanceOf(ApiError);
    });

    it("keeps a newer session when an earlier request is refused", async () => {
        const onUnauthorized = vi.fn();
        let answer;

        global.fetch = vi.fn(
            () =>
                new Promise((resolve) => {
                    answer = resolve;
                }),
        );
        configure({ token: "old-session", onUnauthorized });

        const pending = api.get("/account/me");
        configure({ token: "new-session" });
        answer({ status: 401, ok: false, json: async () => ({ detail: "Sign in." }) });

        await expect(pending).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).not.toHaveBeenCalled();
    });

    it("reports an unauthorized answer once", async () => {
        const onUnauthorized = vi.fn();

        global.fetch = respondWith(401, { code: "error.unauthorized", detail: "Sign in." });
        configure({ token: "expired-session", onUnauthorized });

        await expect(api.get("/users")).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).toHaveBeenCalledOnce();
    });

    it("keeps an anonymous sign-in refusal on the form instead of ending a session", async () => {
        const onUnauthorized = vi.fn();
        configure({ token: null, onUnauthorized });
        global.fetch = respondWith(401, { code: "error.invalid-credentials", detail: "Invalid credentials." });

        await expect(api.post("/admin/signin", { login: "operator", password: "wrong" })).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).not.toHaveBeenCalled();
    });
});

describe("what the server never said", () => {
    it("rejects a successful status carrying an unreadable body", async () => {
        global.fetch = vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.reject(new SyntaxError("Unexpected token <")) });

        await expect(api.get("/account/me")).rejects.toMatchObject({ status: 200, code: "message.unreadableAnswer" });
    });

    it("does not end a reopened session carrying the same token", async () => {
        const response = Promise.withResolvers();
        const onUnauthorized = vi.fn();

        global.fetch = vi.fn().mockReturnValue(response.promise);
        configure({ token: "same-token", onUnauthorized });

        const pending = api.get("/account/me");

        configure({ token: null });
        configure({ token: "same-token" });
        response.resolve({ status: 401, ok: false, json: async () => ({ detail: "Sign in." }) });

        await expect(pending).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).not.toHaveBeenCalled();
    });

    it("is told in the panel's language when a proxy answers a page of its own", async () => {
        // A body too large or a server gone is answered by whatever sits in front, which carries no sentence of ours.
        global.fetch = vi.fn().mockResolvedValue({ status: 502, ok: false, json: () => Promise.reject(new SyntaxError("Unexpected token <")) });
        i18n.global.locale.value = "pt";

        await expect(api.get("/users")).rejects.toMatchObject({ status: 502, code: "message.unreadableAnswer", message: "O servidor respondeu algo que o painel não consegue ler. Tente de novo em instantes." });
    });

    it("is told in the panel's language when the network dropped", async () => {
        global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
        i18n.global.locale.value = "es";

        await expect(api.get("/users")).rejects.toMatchObject({ status: 0, code: "message.unreachable", message: "No se pudo hablar con el servidor. Revisa la conexión e inténtalo de nuevo." });
    });
});
