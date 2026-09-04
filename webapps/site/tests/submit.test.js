import { describe, expect, it, vi } from "vitest";

import { bindSubmits } from "@/submit";

function build() {
    document.body.innerHTML = `
        <form id="one"><button type="submit" name="action" value="accept">Send</button></form>
        <form id="two"><button type="submit">Other</button></form>
    `;

    return document.body;
}

function press(form) {
    const button = form.querySelector("button");
    const event = new Event("submit", { bubbles: true, cancelable: true });

    Object.defineProperty(event, "submitter", { value: button });
    form.dispatchEvent(event);

    return event;
}

describe("sending a form of the site", () => {
    it("marks the button that sent it as busy", () => {
        const root = build();
        const form = root.querySelector("#one");

        bindSubmits(root);
        press(form);

        const button = form.querySelector("button");

        expect(button.hasAttribute("data-busy")).toBe(true);
        expect(button.getAttribute("aria-busy")).toBe("true");
    });

    it("never disables the button, which would drop the value the server reads", () => {
        const root = build();
        const form = root.querySelector("#one");

        bindSubmits(root);
        press(form);

        expect(form.querySelector("button").disabled).toBe(false);
    });

    it("lets the first send leave and stops the second", () => {
        const root = build();
        const form = root.querySelector("#one");

        bindSubmits(root);

        expect(press(form).defaultPrevented).toBe(false);
        expect(press(form).defaultPrevented).toBe(true);
    });

    it("keeps a second listener of the same form from sending it again", () => {
        const root = build();
        const form = root.querySelector("#one");
        const captcha = vi.fn();

        bindSubmits(root);
        form.addEventListener("submit", captcha);

        press(form);
        press(form);

        expect(captcha).toHaveBeenCalledTimes(1);
    });

    it("counts each form of the page on its own", () => {
        const root = build();

        bindSubmits(root);
        press(root.querySelector("#one"));

        expect(press(root.querySelector("#two")).defaultPrevented).toBe(false);
    });

    it("binds nothing on a page with no form", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindSubmits(document.body)).toBe(false);
    });
});
