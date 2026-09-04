import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";

import { THEME_STORAGE_KEY, useThemeStore } from "@/stores/theme";

describe("the palette of the panel", () => {
    beforeEach(() => {
        localStorage.clear();
        document.documentElement.style.colorScheme = "";
    });

    it("follows the device until somebody says otherwise", () => {
        const theme = useThemeStore();

        expect(theme.chosen).toBe("system");
        expect(document.documentElement.style.colorScheme).toBe("light dark");
    });

    it("writes the scheme every palette is read through", () => {
        const theme = useThemeStore();

        theme.choose("dark");
        expect(document.documentElement.style.colorScheme).toBe("dark");

        theme.choose("light");
        expect(document.documentElement.style.colorScheme).toBe("light");

        theme.choose("system");
        expect(document.documentElement.style.colorScheme).toBe("light dark");
    });

    it("carries one press from the device to light, to dark, and back", () => {
        const theme = useThemeStore();

        expect(theme.next()).toBe("light");
        theme.turn();

        expect(theme.next()).toBe("dark");
        theme.turn();

        expect(theme.next()).toBe("system");
        theme.turn();

        expect(theme.chosen).toBe("system");
    });

    it("keeps the choice for the next visit", () => {
        useThemeStore().choose("dark");

        expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    });

    it("draws no palette nobody declared", () => {
        const theme = useThemeStore();

        theme.choose("neon");

        expect(theme.chosen).toBe("system");
    });
});

describe("the panel before it draws", () => {
    // A panel that draws light and then turns is worse than one that waits, so the class is written before the app loads.
    it("writes the palette from the document itself", () => {
        const entry = readFileSync("index.html", "utf8");

        expect(entry).toContain(THEME_STORAGE_KEY);
        expect(entry.indexOf("fastkit_admin_theme")).toBeLessThan(entry.indexOf("/src/main.js"));
    });

    it("names the same key the store keeps it under", () => {
        expect(readFileSync("src/stores/theme.js", "utf8")).toContain(`"${THEME_STORAGE_KEY}"`);
    });
});
