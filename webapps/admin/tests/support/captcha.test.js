import { beforeEach, describe, expect, it, vi } from "vitest";

// The script is loaded once per page and remembered by the module, so every case starts from a page that never asked for it.
async function freshModule() {
    vi.resetModules();

    return await import("@/support/captcha");
}

function fakeDocument(settle = (script) => script.onload()) {
    return { createElement: vi.fn(() => ({})), head: { appendChild: vi.fn(settle) } };
}

describe("recaptcha", () => {
    beforeEach(() => {
        window.grecaptcha = { ready: (callback) => callback(), execute: vi.fn(() => Promise.resolve("token-from-google")) };
    });

    it("mints a token for the attempt", async () => {
        const { mintSignInToken } = await freshModule();

        expect(await mintSignInToken("site-key-1", fakeDocument())).toBe("token-from-google");
        expect(window.grecaptcha.execute).toHaveBeenCalledWith("site-key-1", { action: "admin_signin" });
    });

    it("loads the script once for attempts that arrive while it is still loading", async () => {
        const { mintSignInToken } = await freshModule();
        let finish = null;
        const document = fakeDocument((script) => (finish = script.onload));

        const first = mintSignInToken("site-key-1", document);
        const second = mintSignInToken("site-key-1", document);

        finish();

        expect(await Promise.all([first, second])).toEqual(["token-from-google", "token-from-google"]);
        expect(document.head.appendChild).toHaveBeenCalledTimes(1);
    });

    it("refuses when google will not mint one, so the sign in stops instead of spinning", async () => {
        // Taking no reject left the promise pending for good, and the button waited on it with nothing to say.
        const { mintSignInToken } = await freshModule();

        window.grecaptcha.execute = vi.fn(() => Promise.reject(new Error("google refused")));

        await expect(mintSignInToken("site-key-1", fakeDocument())).rejects.toThrow("google refused");
    });

    it("refuses when the script never loaded, and asks for it again on the next attempt", async () => {
        const { mintSignInToken } = await freshModule();
        const document = fakeDocument((script) => script.onerror());

        await expect(mintSignInToken("site-key-1", document)).rejects.toThrow("recaptcha did not load");

        document.head.appendChild = vi.fn((script) => script.onload());

        expect(await mintSignInToken("site-key-1", document)).toBe("token-from-google");
    });
});
