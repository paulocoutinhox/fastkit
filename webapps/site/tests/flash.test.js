import { describe, expect, it } from "vitest";

import { bindFlashes } from "@/flash";

describe("a notice", () => {
    it("leaves the page when the reader closes it", () => {
        document.body.innerHTML = "<div data-flash><button data-flash-close></button></div>";

        expect(bindFlashes(document.body)).toBe(true);

        document.querySelector("[data-flash-close]").click();

        expect(document.querySelector("[data-flash]")).toBe(null);
    });

    it("binds nothing when the page carries none", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindFlashes(document.body)).toBe(false);
    });
});
