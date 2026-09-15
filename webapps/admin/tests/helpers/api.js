import { vi } from "vitest";

import { api } from "@/api/client";

export const LANGUAGES = [
    { id: 1, name: "English", nativeName: "English", codeIso6391: "en" },
    { id: 2, name: "Portuguese", nativeName: "Português", codeIso6391: "pt" },
    { id: 3, name: "Spanish", nativeName: "Español", codeIso6391: "es" },
];

export const META = { name: "FastKit", environment: "local", version: "1.0.0", storageBaseUrl: "/media", enums: {}, providerCredentials: {}, timezones: [] };

// The panel asks for what it needs and for what this account reaches, so a test that answers only one of them proves nothing.
export function answering(reachable = [], answers = {}) {
    return vi.spyOn(api, "get").mockImplementation((path) => {
        if (path === "/meta") {
            return Promise.resolve(META);
        }

        if (path === "/languages/active") {
            return Promise.resolve(LANGUAGES);
        }

        if (path === "/meta/permissions") {
            return Promise.resolve({ resources: reachable });
        }

        return Promise.resolve(answers[path] ?? { count: 0, items: [] });
    });
}
