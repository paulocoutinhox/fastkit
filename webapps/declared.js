import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const CONFIG = resolve(dirname(fileURLToPath(import.meta.url)), "..", "config", "base.py");

// The server states what it serves and what it looks like, so both builds read it from there and neither writes any of it a second time.
function stated(pattern, what) {
    const found = readFileSync(CONFIG, "utf8").match(pattern);

    if (found === null) {
        throw new Error(`config/base.py no longer declares ${what}, and the build has nowhere to read it from`);
    }

    return found[1];
}

export function declaredPath(name) {
    return stated(new RegExp(`${name}: str = "([^"]+)"`), name);
}

export function declaredBrand() {
    return { hue: Number(stated(/brand_hue: int = (\d+)/, "brand_hue")), chroma: Number(stated(/brand_chroma: float = ([\d.]+)/, "brand_chroma")) };
}

// A step of the ramp is a lightness and how much of the chroma it carries, because a very light or a very dark step holds less of it.
const RAMP = [
    [50, 0.97, 0.11],
    [100, 0.94, 0.21],
    [200, 0.88, 0.37],
    [300, 0.8, 0.58],
    [400, 0.7, 0.79],
    [500, 0.62, 0.95],
    [600, 0.54, 1],
    [700, 0.46, 0.89],
    [800, 0.38, 0.74],
    [900, 0.3, 0.53],
];

export function brandStep(lightness, share) {
    const { hue, chroma } = declaredBrand();

    return `oklch(${lightness} ${(chroma * share).toFixed(3)} ${hue})`;
}

export function brandRamp() {
    return RAMP.map(([name, lightness, share]) => [name, brandStep(lightness, share)]);
}

// The brand is one colour and it does not turn with the palette: a step of it is filled behind white text, and a lighter one behind white text is unreadable.
export function brandSheet() {
    const lines = brandRamp().map(([name, colour]) => `    --brand-${name}: ${colour};`);

    return `/* Written by the build from the brand stated in config/base.py, and never edited here. */\n:root {\n${lines.join("\n")}\n}\n`;
}

// A build writes it before anything reads it, so the stylesheet always compiles against the brand the server declares.
export function brandPlugin(target) {
    return {
        name: "fastkit-brand",
        buildStart() {
            writeFileSync(target, brandSheet());
        },
    };
}
