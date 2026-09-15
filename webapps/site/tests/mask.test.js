import { describe, expect, it } from "vitest";

import { bindMasks, caretAfter, written } from "@/mask";

function build(value = "") {
    document.body.innerHTML = `<input data-mask="(00) 00000-0000" value="${value}" />`;

    return document.body;
}

function type(input, value) {
    input.value = value;
    input.dispatchEvent(new Event("input"));
}

describe("a masked field", () => {
    it("writes the number the way the mask says it is written", () => {
        expect(written("(00) 00000-0000", "21993860010")).toBe("(21) 99386-0010");
    });

    it("carries only as much of the shape as there are digits to fill it", () => {
        expect(written("(00) 00000-0000", "")).toBe("");
        expect(written("(00) 00000-0000", "2")).toBe("(2");
        expect(written("(00) 00000-0000", "21")).toBe("(21");
        expect(written("(00) 00000-0000", "219")).toBe("(21) 9");
    });

    it("drops what is not a digit and never grows past the mask", () => {
        expect(written("(00) 00000-0000", "(21) 99386-0010")).toBe("(21) 99386-0010");
        expect(written("(00) 00000-0000", "21993860010999")).toBe("(21) 99386-0010");
        expect(written("(00) 00000-0000", "abc")).toBe("");
    });

    it("writes what the page already carried", () => {
        const root = build("21993860010");

        expect(bindMasks(root)).toBe(true);
        expect(root.querySelector("input").value).toBe("(21) 99386-0010");
    });

    it("writes as somebody types", () => {
        const root = build();
        bindMasks(root);

        const input = root.querySelector("input");

        type(input, "2199386");

        expect(input.value).toBe("(21) 99386");
    });

    it("puts the caret back where the digits it counted end", () => {
        expect(caretAfter("(21) 99386-0010", 1)).toBe(2);
        expect(caretAfter("(21) 99386-0010", 2)).toBe(3);
        expect(caretAfter("(21) 99386-0010", 3)).toBe(6);
        expect(caretAfter("(21) 99386-0010", 11)).toBe(15);
    });

    it("keeps the caret where somebody was editing instead of throwing it to the end", () => {
        const root = build("21993860010");
        bindMasks(root);

        const input = root.querySelector("input");

        input.value = "(23) 99386-0010";
        input.setSelectionRange(3, 3);
        input.dispatchEvent(new Event("input"));

        expect(input.value).toBe("(23) 99386-0010");
        expect(input.selectionStart).toBe(3);
    });

    it("binds nothing when the page carries none", () => {
        document.body.innerHTML = "<input />";

        expect(bindMasks(document.body)).toBe(false);
    });
});
