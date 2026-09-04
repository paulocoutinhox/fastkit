import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, configure } from "@/api/client";

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

    it("falls back to a generic message when the payload carries none", async () => {
        global.fetch = vi.fn().mockResolvedValue({ status: 500, ok: false, json: () => Promise.reject(new Error("no body")) });

        await expect(api.get("/users")).rejects.toBeInstanceOf(ApiError);
    });

    it("reports an unauthorized answer once", async () => {
        const onUnauthorized = vi.fn();

        global.fetch = respondWith(401, { code: "error.unauthorized", detail: "Sign in." });
        configure({ onUnauthorized });

        await expect(api.get("/users")).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).toHaveBeenCalledOnce();
    });
});
