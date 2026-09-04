import { describe, expect, it } from "vitest";

import { CATALOGS, SUPPORTED_LOCALES, resolveInitialLocale } from "@/i18n";
import en from "@/i18n/en";

function keysOf(catalog, prefix = "") {
    return Object.entries(catalog).flatMap(([name, value]) => (value && typeof value === "object" ? keysOf(value, `${prefix}${name}.`) : [`${prefix}${name}`]));
}

describe("i18n", () => {
    it("is mounted in the suite with every catalogue the panel offers", async () => {
        // Carrying fewer is what let the editor answer two of the three languages without anything noticing.
        const { CATALOGS: harness } = await import("../setup");

        expect(Object.keys(harness).sort()).toEqual([...SUPPORTED_LOCALES].sort());
    });

    it("carries the same keys in every catalog", () => {
        const english = keysOf(en).sort();

        expect(SUPPORTED_LOCALES.length).toBeGreaterThan(1);

        for (const code of SUPPORTED_LOCALES) {
            expect(keysOf(CATALOGS[code]).sort(), `the ${code} catalog drifted`).toEqual(english);
        }
    });

    it("names the same values in every catalog", () => {
        // A screen passes one set of values, so a label naming another is what the reader of that language sees break.
        const slotsOf = (catalog, prefix = "") =>
            Object.entries(catalog).flatMap(([name, value]) =>
                value && typeof value === "object"
                    ? slotsOf(value, `${prefix}${name}.`)
                    : [
                          [
                              `${prefix}${name}`,
                              [...String(value).matchAll(/\{(\w+)\}/g)]
                                  .map((found) => found[1])
                                  .sort()
                                  .join(","),
                          ],
                      ],
            );

        const english = Object.fromEntries(slotsOf(en));
        const differing = [];

        for (const code of SUPPORTED_LOCALES) {
            for (const [key, slots] of slotsOf(CATALOGS[code])) {
                if (english[key] !== slots) {
                    differing.push(`${code}: ${key} names ${slots || "nothing"} where english names ${english[key] || "nothing"}`);
                }
            }
        }

        expect(Object.keys(english).length).toBeGreaterThan(300);
        expect(differing).toEqual([]);
    });

    it("declares every supported locale", () => {
        expect(SUPPORTED_LOCALES).toEqual(["en", "pt", "es"]);
    });

    it("reads a browser asking for spanish", () => {
        expect(resolveInitialLocale(null, "es-ES")).toBe("es");
    });

    it("prefers what was stored", () => {
        expect(resolveInitialLocale("pt", "en-US")).toBe("pt");
    });

    it("falls back to the browser language", () => {
        expect(resolveInitialLocale(null, "pt-BR")).toBe("pt");
        expect(resolveInitialLocale("fr", "pt")).toBe("pt");
    });

    it("ends on english when nothing matches", () => {
        expect(resolveInitialLocale(null, "fr-FR")).toBe("en");
        expect(resolveInitialLocale(null, null)).toBe("en");
    });
});

describe("what a screen asks the catalogue for", () => {
    it("is a key every catalogue holds", async () => {
        const { readFileSync, readdirSync } = await import("node:fs");
        const { join } = await import("node:path");

        const walk = (folder) =>
            readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
                const path = join(folder, entry.name);

                return entry.isDirectory() ? walk(path) : path.endsWith(".vue") || path.endsWith(".js") ? [path] : [];
            });

        // A key drawn where no catalogue holds it reads as `action.format` on the screen, which is what a button of the json field said.
        const asked = new Set();

        for (const path of walk("src")) {
            for (const [, key] of readFileSync(path, "utf8").matchAll(/\$t\(\s*"([a-z][\w]*(?:\.[\w]+)+)"/g)) {
                asked.add(key);
            }
        }

        const held = new Set(keysOf(en));
        const missing = [...asked].filter((key) => !held.has(key)).sort();

        expect(asked.size).toBeGreaterThan(30);
        expect(missing).toEqual([]);
    });
});
