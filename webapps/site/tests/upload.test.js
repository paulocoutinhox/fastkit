import { describe, expect, it } from "vitest";

import { bindUploads } from "@/upload";

function build() {
    document.body.innerHTML = '<label><span class="wrap"><span data-upload-name>No file chosen</span><input type="file" data-upload-input /></span></label>';

    return document.body;
}

function choose(input, name) {
    Object.defineProperty(input, "files", { value: name ? [{ name }] : [], configurable: true });
    input.dispatchEvent(new Event("change"));
}

describe("a file field", () => {
    it("writes the name of what was chosen where the empty label was", () => {
        const root = build();

        expect(bindUploads(root)).toBe(true);

        choose(root.querySelector("[data-upload-input]"), "avatar.png");

        expect(root.querySelector("[data-upload-name]").textContent).toBe("avatar.png");
    });

    it("goes back to the empty label when the choice is taken away", () => {
        const root = build();
        bindUploads(root);

        const input = root.querySelector("[data-upload-input]");

        choose(input, "avatar.png");
        choose(input, null);

        expect(root.querySelector("[data-upload-name]").textContent).toBe("No file chosen");
    });

    it("binds nothing when the page carries none", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindUploads(document.body)).toBe(false);
    });
});
