import { beforeEach, describe, expect, it, vi } from "vitest";

import { bindRecaptcha } from "@/recaptcha";

// The script is loaded once per page and remembered by the module, so every case of the token starts from a page that never asked for it.
async function freshModule() {
    vi.resetModules();

    return await import("@/recaptcha");
}

function fakeDocument(settle = (script) => script.onload()) {
    return { createElement: vi.fn(() => ({})), head: { appendChild: vi.fn(settle) } };
}

function build() {
    document.body.innerHTML = '<form><div data-recaptcha-site-key="key-1"></div><input data-recaptcha-response name="captcha_answer" value="" /></form>';

    return document.body;
}

describe("the recaptcha field", () => {
    it("holds the send back until it carries a token", async () => {
        const root = build();
        const form = root.querySelector("form");

        form.submit = vi.fn();

        expect(bindRecaptcha(root, () => Promise.resolve("token-1"))).toBe(true);

        form.dispatchEvent(new Event("submit", { cancelable: true }));

        await Promise.resolve();
        await Promise.resolve();

        // The token is written before the form leaves, so what the server reads is the answer and never an empty field.
        expect(root.querySelector("[data-recaptcha-response]").value).toBe("token-1");
        expect(form.submit).toHaveBeenCalled();
    });

    it("sends the form anyway when the challenge cannot be minted", async () => {
        // Holding it back left the visitor pressing a button that did nothing, on every public form of the site.
        const root = build();
        const form = root.querySelector("form");

        form.submit = vi.fn();

        bindRecaptcha(root, () => Promise.reject(new Error("google did not answer")));

        form.dispatchEvent(new Event("submit", { cancelable: true }));

        await Promise.resolve();
        await Promise.resolve();

        // The server refuses an empty answer and draws the page again with the reason, which is a refusal somebody can read.
        expect(root.querySelector("[data-recaptcha-response]").value).toBe("");
        expect(form.submit).toHaveBeenCalled();
    });

    it("lets a form that already carries a token through", () => {
        const root = build();
        const form = root.querySelector("form");

        root.querySelector("[data-recaptcha-response]").value = "already";
        form.submit = vi.fn();

        bindRecaptcha(root, () => Promise.resolve("token-2"));

        const event = new Event("submit", { cancelable: true });
        form.dispatchEvent(event);

        expect(event.defaultPrevented).toBe(false);
        expect(form.submit).not.toHaveBeenCalled();
    });

    it("binds nothing on a page with no challenge", () => {
        document.body.innerHTML = "<form></form>";

        expect(bindRecaptcha(document.body, () => Promise.resolve(""))).toBe(false);
    });
});

describe("the token a public form is sent with", () => {
    beforeEach(() => {
        window.grecaptcha = { ready: (callback) => callback(), execute: vi.fn(() => Promise.resolve("token-1")) };
    });

    it("asks google for its script the first time a form is sent, since no page loads it for the site", async () => {
        const { mintToken } = await freshModule();
        const document = fakeDocument();

        expect(await mintToken("site-key-1", document)).toBe("token-1");
        expect(document.head.appendChild).toHaveBeenCalledTimes(1);
        expect(window.grecaptcha.execute).toHaveBeenCalledWith("site-key-1", { action: "submit" });
    });

    it("refuses when google will not mint one, so the form leaves instead of waiting for good", async () => {
        // Taking no reject left the promise pending, and the send that waits on it never happened at all.
        const { mintToken } = await freshModule();

        window.grecaptcha.execute = () => Promise.reject(new Error("google refused"));

        await expect(mintToken("site-key-1", fakeDocument())).rejects.toThrow("google refused");
    });
});
