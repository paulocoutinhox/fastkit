import { describe, expect, it } from "vitest";

import { bindMenu } from "@/menu";

function build(markup) {
    document.body.innerHTML = markup;

    return document.body;
}

describe("the menu of a narrow screen", () => {
    it("opens and closes on the button", () => {
        const root = build('<button data-menu-toggle></button><nav data-menu class="hidden"></nav>');

        expect(bindMenu(root)).toBe(true);

        root.querySelector("[data-menu-toggle]").click();

        expect(root.querySelector("[data-menu]").classList.contains("hidden")).toBe(false);

        root.querySelector("[data-menu-toggle]").click();

        expect(root.querySelector("[data-menu]").classList.contains("hidden")).toBe(true);
    });

    it("keeps the column the header laid out", () => {
        // The nav is a column on a narrow screen, so opening it must not take that away.
        const root = build('<button data-menu-toggle></button><nav data-menu class="hidden flex-col"></nav>');

        bindMenu(root);
        root.querySelector("[data-menu-toggle]").click();

        const nav = root.querySelector("[data-menu]");

        expect(nav.classList.contains("flex")).toBe(true);
        expect(nav.classList.contains("flex-col")).toBe(true);
    });

    it("says whether it is open", () => {
        const root = build('<button data-menu-toggle></button><nav data-menu class="hidden"></nav>');

        bindMenu(root);

        const toggle = root.querySelector("[data-menu-toggle]");

        expect(toggle.getAttribute("aria-expanded")).toBe("false");

        toggle.click();
        expect(toggle.getAttribute("aria-expanded")).toBe("true");

        toggle.click();
        expect(toggle.getAttribute("aria-expanded")).toBe("false");
    });

    it("binds nothing on a page that draws no menu", () => {
        expect(bindMenu(build("<div></div>"))).toBe(false);
    });
});
