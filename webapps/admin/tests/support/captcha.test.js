import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadRecaptcha, mintRecaptcha } from "@/support/captcha";

function fakeDocument() {
    const head = { appendChild: vi.fn((script) => script.onload()) };

    return { querySelector: vi.fn(() => null), createElement: vi.fn(() => ({})), head };
}

describe("recaptcha", () => {
    beforeEach(() => {
        window.grecaptcha = { ready: (callback) => callback(), execute: vi.fn(() => Promise.resolve("token-from-google")) };
    });

    it("loads the script once and mints a token for the attempt", async () => {
        const document = fakeDocument();

        expect(await mintRecaptcha("site-key-1", document)).toBe("token-from-google");
        expect(document.head.appendChild).toHaveBeenCalledTimes(1);
        expect(window.grecaptcha.execute).toHaveBeenCalledWith("site-key-1", { action: "admin_signin" });
    });

    it("reuses the script the page already carries", async () => {
        const document = fakeDocument();
        document.querySelector = vi.fn(() => ({}));

        await loadRecaptcha("site-key-1", document);

        expect(document.head.appendChild).not.toHaveBeenCalled();
    });

    it("refuses when google will not mint one, so the sign in stops instead of spinning", async () => {
        // Taking no reject left the promise pending for good, and the button waited on it with nothing to say.
        window.grecaptcha.execute = vi.fn(() => Promise.reject(new Error("google refused")));

        await expect(mintRecaptcha("site-key-1", fakeDocument())).rejects.toThrow("google refused");
    });

    it("refuses when the script never loaded", async () => {
        const document = fakeDocument();
        document.head.appendChild = vi.fn((script) => script.onerror());

        await expect(loadRecaptcha("site-key-1", document)).rejects.toThrow("recaptcha did not load");
    });
});
