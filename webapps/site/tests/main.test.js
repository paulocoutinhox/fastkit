import { describe, expect, it, vi } from "vitest";

import { grecaptchaToken } from "@/main";

function google(execute) {
    window.grecaptcha = { ready: (callback) => callback(), execute };
}

describe("the token a public form is sent with", () => {
    it("answers what google minted", async () => {
        google(vi.fn(() => Promise.resolve("token-1")));

        expect(await grecaptchaToken("site-key-1")).toBe("token-1");
        expect(window.grecaptcha.execute).toHaveBeenCalledWith("site-key-1", { action: "submit" });
    });

    it("refuses when google will not mint one, so the form leaves instead of waiting for good", async () => {
        // Taking no reject left the promise pending, and the send that waits on it never happened at all.
        google(() => Promise.reject(new Error("google refused")));

        await expect(grecaptchaToken("site-key-1")).rejects.toThrow("google refused");
    });
});
