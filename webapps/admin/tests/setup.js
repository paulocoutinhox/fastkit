import { createPinia, setActivePinia } from "pinia";
import { beforeEach, vi } from "vitest";
import { createI18n } from "vue-i18n";

import en from "@/i18n/en";
import es from "@/i18n/es";
import pt from "@/i18n/pt";
import { config } from "@vue/test-utils";

// The catalogues are named here rather than read off the panel, because that module asks the browser for the stored locale the moment it is imported.
export const CATALOGS = { en, pt, es };

export const i18n = createI18n({ legacy: false, globalInjection: true, locale: "en", fallbackLocale: "en", messages: CATALOGS });

// Node ships an experimental localStorage that shadows the one jsdom builds, so the tests own theirs.
class MemoryStorage {
    constructor() {
        this.entries = new Map();
    }

    getItem(key) {
        return this.entries.has(key) ? this.entries.get(key) : null;
    }

    setItem(key, value) {
        this.entries.set(key, String(value));
    }

    removeItem(key) {
        this.entries.delete(key);
    }

    clear() {
        this.entries.clear();
    }
}

const storage = new MemoryStorage();

Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true, writable: true });
Object.defineProperty(window, "localStorage", { value: storage, configurable: true, writable: true });

// The editor asks the browser which device it is running on, which jsdom does not answer.
window.matchMedia = (query) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null });

const RouterLinkStub = { props: { to: { type: [String, Object], required: true } }, template: "<a><slot /></a>" };

config.global.plugins = [i18n];
config.global.stubs = { RouterLink: RouterLinkStub, Teleport: true, Transition: false, TransitionGroup: false };

beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    i18n.global.locale.value = "en";
    vi.restoreAllMocks();
});
