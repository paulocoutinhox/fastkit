import { describe, expect, it } from "vitest";

import { sortByLabel } from "@/support/sorting";

function labels(items) {
    return items.map((item) => item.label);
}

describe("sortByLabel", () => {
    it("ignores accents and case", () => {
        const items = [{ label: "Zebra" }, { label: "Ébano" }, { label: "abacate" }];

        expect(labels(sortByLabel(items, "pt"))).toEqual(["abacate", "Ébano", "Zebra"]);
    });

    it("reads a run of digits as a number", () => {
        const items = [{ label: "item 10" }, { label: "item 2" }, { label: "item 1" }];

        expect(labels(sortByLabel(items, "pt"))).toEqual(["item 1", "item 2", "item 10"]);
    });

    it("leaves the given list untouched", () => {
        const items = [{ label: "b" }, { label: "a" }];
        sortByLabel(items, "en");

        expect(labels(items)).toEqual(["b", "a"]);
    });
});
