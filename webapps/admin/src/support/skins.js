import darkSkin from "tinymce/skins/ui/oxide-dark/skin.css?raw";
import lightSkin from "tinymce/skins/ui/oxide/skin.css?raw";

// The editor is drawn in a navy and a blue of its own, so each tone of those two families is read as the role the panel gives it.
// The dark skin paints its surfaces and borders in the navy.
export const SURFACES = {
    "0c1116": "--color-line-strong",
    "0e141a": "--color-line-strong",
    "161f29": "--color-line-strong",
    264972: "--color-line-strong",
    324053: "--color-line-strong",
    "364a62": "--color-line-strong",
    "17202a": "--color-surface",
    "19232e": "--color-surface",
    "202d3b": "--color-surface",
    "222f3e": "--color-raised",
    "2b3b4e": "--color-highlight",
    "2f4055": "--color-sunken",
    "1f354f": "--color-lifted",
    254161: "--color-lifted",
    "34485f": "--color-lifted",
    "3d546f": "--color-lifted",
    "4e5965": "--color-lifted",
};

// The light skin writes its text in the same navy.
export const INKS = {
    "071729": "--color-ink",
    "0b1a2c": "--color-ink",
    163355: "--color-ink",
    "222f3e": "--color-ink",
};

// Both mark focus, selection and the active tab in the blue, and the panel marks those in its neutral roles, keeping the brand for the button a screen asks to be pressed.
// The lightest tints are the surfaces of a selection, the middle ones the rings of focus, and the darker ones the words and the underline of what is chosen.
export const ACCENTS = {
    d9edf7: "--color-highlight",
    e6f0fd: "--color-highlight",
    e8f1f8: "--color-highlight",
    b4d7ff: "--color-lifted",
    c1dbf9: "--color-lifted",
    cce2fa: "--color-lifted",
    cde5ff: "--color-lifted",
    d6e7fb: "--color-lifted",
    "99c4f5": "--color-line-strong",
    a6ccf7: "--color-line-strong",
    a8c8ed: "--color-line-strong",
    "67aeff": "--color-ink-faint",
    "77b1f2": "--color-ink-faint",
    "7daee4": "--color-ink-faint",
    "83b7f3": "--color-ink-faint",
    "8ebef4": "--color-ink-faint",
    "93bbe9": "--color-ink-faint",
    "4099ff": "--color-ink-faint",
    "4292ed": "--color-ink-faint",
    "599fef": "--color-ink-faint",
    "2681ea": "--color-ink-faint",
    "2b85eb": "--color-ink-faint",
    "006ce7": "--color-ink",
    "086be6": "--color-ink",
    "0060ce": "--color-ink",
    "1368c9": "--color-ink",
    "285ec7": "--color-ink",
    "2a64a6": "--color-ink",
    "0054b4": "--color-ink",
    144782: "--color-ink",
    "254f80": "--color-ink",
    "2b5c93": "--color-ink",
    "003c81": "--color-ink",
    "00489b": "--color-ink",
    "1b3b60": "--color-ink",
    "1f436c": "--color-ink",
};

function hexOf(red, green, blue) {
    return [red, green, blue].map((channel) => Number(channel).toString(16).padStart(2, "0")).join("");
}

function tinted(variable, alpha) {
    return alpha === undefined ? `var(${variable})` : `rgb(from var(${variable}) r g b / ${alpha})`;
}

// A colour of those families is read however the skin writes it, with an alpha of its own or without one, and every other colour stays as the skin wrote it.
export function repaint(css, tones) {
    return css
        .replace(/#([0-9a-f]{6})([0-9a-f]{2})?\b/gi, (written, hex, alpha) => {
            const variable = tones[hex.toLowerCase()];

            if (!variable) {
                return written;
            }

            return tinted(variable, alpha === undefined ? undefined : Number((parseInt(alpha, 16) / 255).toFixed(3)));
        })
        .replace(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/g, (written, red, green, blue, alpha) => {
            const variable = tones[hexOf(red, green, blue)];

            return variable ? tinted(variable, alpha) : written;
        });
}

export const SKINS = { light: repaint(lightSkin, { ...INKS, ...ACCENTS }), dark: repaint(darkSkin, { ...SURFACES, ...ACCENTS }) };
