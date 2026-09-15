import { describe, expect, it, vi } from "vitest";

import { bindPostalCode } from "@/postal-code";

function build(offered = "BR") {
    document.body.innerHTML = `
        <form data-address-form data-postal-code-url="/account/address/postal-code" data-postal-code-countries="${offered}">
            <select name="country_code"><option value="BR" selected>Brazil</option><option value="GB">United Kingdom</option></select>
            <input name="postal_code" value="01001000" />
            <span data-postal-code-status class="hidden"></span>
            <input name="line1" value="" />
            <input name="district" value="" />
            <input name="city" value="Somewhere else" />
            <input name="state" value="" />
        </form>
    `;

    return document.body;
}

const FOUND = { line1: "Praça da Sé", district: "Sé", city: "São Paulo", state: "SP" };

describe("the postal code of an address", () => {
    it("fills only what is still empty", async () => {
        const root = build();
        const lookup = vi.fn().mockResolvedValue(FOUND);

        expect(bindPostalCode(root, lookup)).toBe(true);

        root.querySelector('[name="postal_code"]').dispatchEvent(new Event("blur"));
        await vi.waitFor(() => expect(lookup).toHaveBeenCalled());

        expect(root.querySelector('[name="line1"]').value).toBe("Praça da Sé");
        expect(root.querySelector('[name="city"]').value).toBe("Somewhere else");
    });

    it("asks nobody for a country that has nobody to ask", () => {
        const root = build("BR");
        const lookup = vi.fn();

        bindPostalCode(root, lookup);
        root.querySelector('[name="country_code"]').value = "GB";
        root.querySelector('[name="postal_code"]').dispatchEvent(new Event("blur"));

        expect(lookup).not.toHaveBeenCalled();
    });

    it("puts the waiting notice away when nothing was found", async () => {
        const root = build();
        const lookup = vi.fn().mockResolvedValue(null);

        bindPostalCode(root, lookup);
        root.querySelector('[name="postal_code"]').dispatchEvent(new Event("blur"));

        await vi.waitFor(() => expect(root.querySelector("[data-postal-code-status]").classList.contains("hidden")).toBe(true));
    });

    it("fills the address of the code the visitor last asked about", async () => {
        // A field is only filled while it is empty, so the older answer arriving first would settle a code the visitor already replaced.
        const root = build();
        let settleSecond;

        const lookup = vi
            .fn()
            .mockResolvedValueOnce({ line1: "First street", district: "First", city: "First city", state: "FC" })
            .mockImplementationOnce(() => new Promise((resolve) => (settleSecond = resolve)));

        bindPostalCode(root, lookup);

        const code = root.querySelector('[name="postal_code"]');

        code.value = "11111111";
        code.dispatchEvent(new Event("blur"));
        code.value = "22222222";
        code.dispatchEvent(new Event("blur"));

        await vi.waitFor(() => expect(lookup).toHaveBeenCalledTimes(2));
        await Promise.resolve();

        expect(root.querySelector('[name="line1"]').value).toBe("");

        settleSecond({ line1: "Second street", district: "Second", city: "Second city", state: "SC" });

        await vi.waitFor(() => expect(root.querySelector('[name="line1"]').value).toBe("Second street"));
    });

    it("binds nothing on a page with no address form", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindPostalCode(document.body, vi.fn())).toBe(false);
    });
});
