import { vi } from "vitest";

import { api } from "@/api/client";

export const META = { name: "FastKit", environment: "local", version: "1.0.0", storageBaseUrl: "/media", enums: {}, captcha: { provider: "disabled", siteKey: "" }, providerCredentials: {}, timezones: [] };

// The panel asks for what it needs and for what this account reaches, so a test that answers only one of them proves nothing.
export function answering(reachable = [], answers = {}) {
    return vi.spyOn(api, "get").mockImplementation((path) => {
        if (path === "/meta") {
            return Promise.resolve(META);
        }

        if (path === "/meta/permissions") {
            return Promise.resolve({ resources: reachable });
        }

        return Promise.resolve(answers[path] ?? { count: 0, items: [] });
    });
}
