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

        theme.chosen = "dark";
        expect(document.documentElement.style.colorScheme).toBe("dark");

        theme.chosen = "light";
        expect(document.documentElement.style.colorScheme).toBe("light");

        theme.chosen = "system";
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
        const theme = useThemeStore();

        theme.turn();
        theme.turn();

        expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    });

    it("says whether the panel is drawn dark, for the frames that cannot read its palette", () => {
        const theme = useThemeStore();

        theme.chosen = "dark";
        expect(theme.dark).toBe(true);

        theme.chosen = "light";
        expect(theme.dark).toBe(false);

        theme.chosen = "system";
        expect(theme.dark).toBe(matchMedia("(prefers-color-scheme: dark)").matches);
    });

    it("hears the device turn dark while the panel is open", () => {
        let turn = null;
        const device = window.matchMedia;

        window.matchMedia = (query) => ({ matches: false, media: query, addEventListener: (event, heard) => (turn = heard), removeEventListener: () => {} });

        const theme = useThemeStore();

        expect(theme.dark).toBe(false);

        turn({ matches: true });

        expect(theme.dark).toBe(true);

        window.matchMedia = device;
    });
});

describe("the panel before it draws", () => {
    // A panel that draws light and then turns is worse than one that waits, so the class is written before the app loads.
    it("writes the palette from the document itself", () => {
        const entry = readFileSync("index.html", "utf8");

        expect(entry).toContain(THEME_STORAGE_KEY);
        expect(entry.indexOf(THEME_STORAGE_KEY)).toBeLessThan(entry.indexOf("/src/main.js"));
    });

    it("names the same key the store keeps it under", () => {
        expect(readFileSync("src/stores/theme.js", "utf8")).toContain(`"${THEME_STORAGE_KEY}"`);
    });
});
