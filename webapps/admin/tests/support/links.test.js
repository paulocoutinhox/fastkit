import { describe, expect, it } from "vitest";

import { API_PATH } from "@/api/client";
import { contentOnSite, webhookUrl } from "@/support/links";

describe("contentOnSite", () => {
    it("is the tag and nothing else, which is the one address the site answers it at", () => {
        // A page of the site carries neither the tenant nor the language, so an address that did pointed at nothing.
        expect(contentOnSite({ tag: "termos", tenant: { code: "storycloud" }, language: { codeIso6391: "pt" } })).toBe("/content/termos");
    });

    it("says the same for a content every tenant reaches", () => {
        expect(contentOnSite({ tag: "termos", tenant: null, language: null })).toBe("/content/termos");
    });

    it("answers nothing without a tag", () => {
        expect(contentOnSite({ tag: "", tenant: { code: "storycloud" } })).toBe("");
    });
});

describe("webhookUrl", () => {
    it("is one address per integration, which is what tells one tenant's gateway from another's", () => {
        expect(webhookUrl({ webhookKey: "chave-1" })).toBe(`${window.location.origin}${API_PATH}/webhooks/chave-1`);
        expect(webhookUrl({ webhookKey: "chave-2" })).toBe(`${window.location.origin}${API_PATH}/webhooks/chave-2`);
    });

    it("reads where the api answers from the build, because an operator pastes this into a gateway console", () => {
        // Written by hand, moving `api_path` would wire every integration to nothing and say so nowhere.
        expect(webhookUrl({ webhookKey: "chave-1" })).toContain(API_PATH);
    });

    it("answers empty where there is no key, so the icon is never drawn on nothing", () => {
        expect(webhookUrl({})).toBe("");
        expect(webhookUrl({ webhookKey: "" })).toBe("");
    });
});
