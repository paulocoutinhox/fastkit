import { describe, expect, it, vi } from "vitest";

import { bindRecaptcha } from "@/recaptcha";

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
