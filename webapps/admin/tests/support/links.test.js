import { describe, expect, it } from "vitest";

import { API_PATH } from "@/api/client";
import { contentOnSite, webhookUrl } from "@/support/links";

describe("contentOnSite", () => {
    it("is the address the server answered, which is on the site of the brand the page belongs to", () => {
        // The panel may be open on any brand's domain, so the host it was opened on says nothing about where a page lives.
        expect(contentOnSite({ tag: "termos", address: "https://storycloud.example/content/termos" })).toBe("https://storycloud.example/content/termos");
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
