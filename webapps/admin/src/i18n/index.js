import { createI18n } from "vue-i18n";

import en from "./en";
import es from "./es";
import pt from "./pt";

export const CATALOGS = { en, pt, es };

// What the admin offers is which catalogs it carries, so adding a language is adding a file and naming it above.
export const SUPPORTED_LOCALES = Object.keys(CATALOGS);
export const LOCALE_STORAGE_KEY = "fastkit.locale";

export function resolveInitialLocale(stored, navigatorLanguage) {
    if (SUPPORTED_LOCALES.includes(stored)) {
        return stored;
    }

    const primary = (navigatorLanguage || "en").toLowerCase().split("-")[0];

    return SUPPORTED_LOCALES.includes(primary) ? primary : "en";
}

export const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    locale: resolveInitialLocale(localStorage.getItem(LOCALE_STORAGE_KEY), navigator.language),
    fallbackLocale: "en",
    messages: CATALOGS,
});
