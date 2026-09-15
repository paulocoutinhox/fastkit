import { describe, expect, it } from "vitest";

import { bindLightbox } from "@/lightbox";

function build(count = 2) {
    const photos = Array.from({ length: count }, (_, index) => `<a href="/media/p${index}.webp" data-lightbox="Photo ${index}"><img /></a>`).join("");
    const words = '<span data-lightbox-words data-close="Fechar" data-previous="Foto anterior" data-next="Próxima foto"></span>';
    document.body.innerHTML = `<div>${words}${photos}</div>`;

    // The page binds the document itself, which is the one root whose `ownerDocument` is null.
    return document;
}

describe("the words of the lightbox", () => {
    it("come from the page, so a gallery is read in the language it was drawn in", () => {
        bindLightbox(build());

        const named = [...frame().querySelectorAll("[data-lightbox-label]")].map((button) => button.getAttribute("aria-label"));

        expect(named).toEqual(["Fechar", "Foto anterior", "Próxima foto"]);
    });
});

function frame() {
    return document.querySelector("dialog");
}

describe("a photo of a gallery", () => {
    it("opens over the page instead of leaving it", () => {
        const root = build();

        expect(bindLightbox(root)).toBe(true);

        root.querySelectorAll("[data-lightbox]")[1].click();

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p1.webp");
        expect(frame().querySelector("[data-lightbox-caption]").textContent).toBe("Photo 1");
    });

    it("walks to the next one and wraps around at the end", () => {
        const root = build();
        bindLightbox(root);

        root.querySelector("[data-lightbox]").click();
        frame().querySelector("[data-lightbox-next]").click();

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p1.webp");

        frame().querySelector("[data-lightbox-next]").click();

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p0.webp");
    });

    it("walks back from the first one to the last", () => {
        const root = build();
        bindLightbox(root);

        root.querySelector("[data-lightbox]").click();
        frame().querySelector("[data-lightbox-previous]").click();

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p1.webp");
    });

    it("answers the arrow keys", () => {
        const root = build();
        bindLightbox(root);

        root.querySelector("[data-lightbox]").click();
        frame().dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p1.webp");

        frame().dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" }));

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p0.webp");
    });

    it("ignores a key that means nothing here", () => {
        const root = build();
        bindLightbox(root);

        root.querySelector("[data-lightbox]").click();
        frame().dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));

        expect(frame().querySelector("[data-lightbox-image]").getAttribute("src")).toBe("/media/p0.webp");
    });

    it("closes on the button and on the ground beside the photo", () => {
        const root = build();
        bindLightbox(root);

        root.querySelector("[data-lightbox]").click();
        frame().querySelector("[data-lightbox-close]").click();

        expect(frame().open).toBe(false);

        root.querySelector("[data-lightbox]").click();
        frame().click();

        expect(frame().open).toBe(false);
    });

    it("binds nothing on a page with no photos", () => {
        document.body.innerHTML = "<div></div>";

        expect(bindLightbox(document)).toBe(false);
    });
});
