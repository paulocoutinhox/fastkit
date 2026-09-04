import { describe, expect, it } from "vitest";

import { dependentsOf, isWaiting, narrowingFilters, parentsOf, valueAt } from "@/support/dependencies";

const CHAIN = [{ name: "country_id" }, { name: "state_id", dependsOn: "country_id" }, { name: "city_id", dependsOn: "state_id" }, { name: "district_id", dependsOn: "city_id" }, { name: "unrelated" }];

describe("parentsOf", () => {
    it("reads a single name and a list of them the same way", () => {
        expect(parentsOf({ dependsOn: "country_id" })).toEqual(["country_id"]);
        expect(parentsOf({ dependsOn: ["country_id", "languageId"] })).toEqual(["country_id", "languageId"]);
    });

    it("answers nothing for a field that hangs off no other", () => {
        expect(parentsOf({ name: "title" })).toEqual([]);
    });
});

describe("isWaiting", () => {
    it("waits while any parent is empty", () => {
        expect(isWaiting({ dependsOn: ["a", "b"] }, { a: 1, b: null })).toBe(true);
        expect(isWaiting({ dependsOn: "a" }, {})).toBe(true);
        expect(isWaiting({ dependsOn: "a" }, { a: "" })).toBe(true);
    });

    it("stops waiting once every parent answers", () => {
        expect(isWaiting({ dependsOn: ["a", "b"] }, { a: 1, b: 2 })).toBe(false);
    });

    it("never waits when it depends on nothing", () => {
        expect(isWaiting({ name: "title" }, {})).toBe(false);
    });
});

describe("narrowingFilters", () => {
    it("turns what the parents hold into the filter of the query", () => {
        expect(narrowingFilters({ dependsOn: ["a", "b"] }, { a: 1, b: 2, c: 3 })).toEqual({ a: 1, b: 2 });
    });

    it("sends the filter under the name the dependent resource asks it by", () => {
        const field = { dependsOn: "entitlementId", filterAs: { entitlementId: "reachable_by_entitlement" } };

        expect(narrowingFilters(field, { entitlementId: 7 })).toEqual({ reachable_by_entitlement: 7 });
    });

    it("keeps the parent name when nothing renames it", () => {
        expect(narrowingFilters({ dependsOn: "a", filterAs: { b: "other" } }, { a: 1 })).toEqual({ a: 1 });
    });

    it("narrows by nothing when it depends on nothing", () => {
        expect(narrowingFilters({ name: "title" }, { a: 1 })).toEqual({});
    });
});

describe("dependentsOf", () => {
    it("reaches every level below, however deep the chain runs", () => {
        expect(dependentsOf(CHAIN, "country_id")).toEqual(["state_id", "city_id", "district_id"]);
    });

    it("starts from the level that moved and never above it", () => {
        expect(dependentsOf(CHAIN, "city_id")).toEqual(["district_id"]);
    });

    it("answers nothing for a level nothing hangs off", () => {
        expect(dependentsOf(CHAIN, "district_id")).toEqual([]);
        expect(dependentsOf(CHAIN, "unrelated")).toEqual([]);
    });

    it("reaches a field only once when several parents lead to it", () => {
        const fields = [{ name: "a" }, { name: "b", dependsOn: "a" }, { name: "c", dependsOn: ["a", "b"] }];

        expect(dependentsOf(fields, "a")).toEqual(["b", "c"]);
    });
});

describe("valueAt", () => {
    it("reaches into what the api expanded", () => {
        expect(valueAt({ subscription: { user: { displayName: "Ada" } } }, "subscription.user.displayName")).toBe("Ada");
    });

    it("answers null when the path stops short", () => {
        expect(valueAt({ subscription: null }, "subscription.user.displayName")).toBeNull();
        expect(valueAt({}, "subscription.user.displayName")).toBeNull();
    });
});
