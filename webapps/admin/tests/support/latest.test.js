import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { newest } from "@/support/latest";

function walk(folder) {
    return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
        const full = `${folder}/${entry.name}`;

        if (entry.isDirectory()) {
            return walk(full);
        }

        return /\.(vue|js)$/.test(entry.name) ? [full] : [];
    });
}

describe("the newest answer", () => {
    it("calls every attempt but the last one stale", () => {
        const answers = newest();
        const first = answers.take();
        const second = answers.take();

        expect(answers.stale(first)).toBe(true);
        expect(answers.stale(second)).toBe(false);
    });

    it("starts fresh for each caller, so one screen never ages the answers of another", () => {
        const mine = newest();
        const yours = newest();
        const attempt = mine.take();

        yours.take();

        expect(mine.stale(attempt)).toBe(false);
    });

    // Four screens overlap their requests, and the same counter written by hand in each is four chances to write it differently.
    it("is the only place a request is counted", () => {
        const written = walk("src")
            .filter((path) => path !== "src/support/latest.js")
            .map((path) => [path, readFileSync(path, "utf8")])
            .filter(([, source]) => /\bapi\.\w+\(/.test(source) && /let \w*[sS]equence|[sS]equence \+= 1|let attempt = 0/.test(source))
            .map(([path]) => path);

        expect(walk("src").length).toBeGreaterThan(50);
        expect(written).toEqual([]);
    });
});
