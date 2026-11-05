import { describe, expect, it } from "vitest";

import { ACCENTS, INKS, SKINS, SURFACES, repaint } from "@/support/skins";

// The hue slider and the swatches are colours the skin draws as themselves, and never a part of its theme.
const DRAWN_AS_THEMSELVES = ["0080ff", "8000ff", "851aff", "55367a", "8864ad", "c290fb"];

function blueTinted(css) {
    return [...new Set([...css.matchAll(/#([0-9a-f]{6})\b/gi)].map((found) => found[1].toLowerCase()))].filter((hex) => {
        const [red, green, blue] = [0, 2, 4].map((at) => parseInt(hex.slice(at, at + 2), 16));

        return blue - red >= 20 && blue >= green;
    });
}

describe("the skins of the editor", () => {
    it("reads a tone of the navy or the blue as the role the panel gives it, however it is written", () => {
        const tones = { "222f3e": "--color-raised", "006ce7": "--brand-600" };

        expect(repaint("a { color: #222F3E; }", tones)).toBe("a { color: var(--color-raised); }");
        expect(repaint("a { color: #222f3e12; }", tones)).toBe("a { color: rgb(from var(--color-raised) r g b / 0.071); }");
        expect(repaint("a { color: rgba(0, 108, 231, 0.2); }", tones)).toBe("a { color: rgb(from var(--brand-600) r g b / 0.2); }");
    });

    it("leaves every other colour as the skin wrote it", () => {
        expect(repaint("a { color: #c00; background: #e74c3c; border: rgba(204, 0, 0, 0.2); }", SURFACES)).toBe("a { color: #c00; background: #e74c3c; border: rgba(204, 0, 0, 0.2); }");
    });

    it("leaves no tone of the navy or the blue behind in either skin", () => {
        // A new release of the editor that brings a tone nobody mapped is a remnant of its own palette, and this is where it is seen.
        for (const [name, css] of Object.entries(SKINS)) {
            expect(css.length, name).toBeGreaterThan(100000);
            expect(
                blueTinted(css).filter((hex) => !DRAWN_AS_THEMSELVES.includes(hex)),
                name,
            ).toEqual([]);
            expect(css, name).not.toMatch(/rgba\((34,\s*47,\s*62|0,\s*108,\s*231),/);
        }
    });

    it("names only roles the panel declares", () => {
        const declared = [...Object.values(SURFACES), ...Object.values(INKS)];

        expect(declared.every((role) => /^--color-(surface|raised|sunken|highlight|lifted|line-strong|ink)$/.test(role))).toBe(true);
        // The panel marks focus and selection in its neutral roles, so no accent of the editor turns into the brand.
        expect(Object.values(ACCENTS).every((role) => /^--color-(highlight|lifted|line-strong|ink-faint|ink)$/.test(role))).toBe(true);
    });
});
