import { describe, expect, it, vi } from "vitest";

import { bindConsent } from "@/consent";

function build() {
    document.body.innerHTML = `
        <div data-consent>
            <form method="post" action="/cookies">
                <input type="hidden" name="csrf_token" value="a-token" />
                <button type="submit" name="action" value="reject">Only the necessary</button>
                <button type="submit" name="action" value="accept">Allow everything</button>
            </form>
        </div>
    `;

    return document.body;
}

function answer(root, value) {
    const form = root.querySelector("form");
    const submitter = root.querySelector(`[value="${value}"]`);
    const event = new Event("submit", { cancelable: true });

    Object.defineProperty(event, "submitter", { value: submitter });
    form.dispatchEvent(event);

    return event;
}

describe("the cookie notice", () => {
    it("sends the answer and takes itself off the page", async () => {
        const root = build();
        const send = vi.fn().mockResolvedValue({});

        expect(bindConsent(root, send)).toBe(true);

        answer(root, "accept");

        expect(send).toHaveBeenCalledWith("/cookies", expect.anything());
        expect(send.mock.calls[0][1].get("action")).toBe("accept");

        await vi.waitFor(() => expect(root.querySelector("[data-consent]")).toBe(null));
    });

    it("carries the button that was pressed and not the other one", () => {
        const root = build();
        const send = vi.fn().mockResolvedValue({});

        bindConsent(root, send);
        answer(root, "reject");

        expect(send.mock.calls[0][1].get("action")).toBe("reject");
    });

    it("lets the form go the usual way when nothing said which button", () => {
        const root = build();
        const send = vi.fn();
        const form = root.querySelector("form");
        const event = new Event("submit", { cancelable: true });

        Object.defineProperty(event, "submitter", { value: null });
        form.dispatchEvent(event);

        expect(send).not.toHaveBeenCalled();
        expect(event.defaultPrevented).toBe(false);
    });

    it("binds nothing on a page that carries no notice", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindConsent(document.body, vi.fn())).toBe(false);
    });
});
