import { createI18n } from "vue-i18n";

import en from "./en";
import es from "./es";
import pt from "./pt";
import { configure } from "@/api/client";

export const CATALOGS = { en, pt, es };

// What the admin offers is which catalogs it carries, so adding a language is adding a file and naming it above.
export const SUPPORTED_LOCALES = Object.keys(CATALOGS);
export const LOCALE_STORAGE_KEY = "admin.locale";

export function resolveInitialLocale(stored, navigatorLanguage) {
    if (SUPPORTED_LOCALES.includes(stored)) {
        return stored;
    }

    const primary = navigatorLanguage?.toLowerCase().split("-")[0];

    return SUPPORTED_LOCALES.includes(primary) ? primary : "en";
}

// The panel, the next visit and every answer of the api turn together, so a language is only ever changed here.
export function speak(locale, code) {
    locale.value = code;
    // A screen reader and a browser translation read the page in the language it says it is in.
    document.documentElement.lang = code;
    localStorage.setItem(LOCALE_STORAGE_KEY, code);
    configure({ locale: code });
}

export const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    locale: resolveInitialLocale(localStorage.getItem(LOCALE_STORAGE_KEY), navigator.language),
    messages: CATALOGS,
});
