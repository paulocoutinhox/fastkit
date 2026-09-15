const DATE_TIME_LENGTH = 16;

export function resolveTimezone(preferred) {
    return preferred || Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function parts(value, timezone) {
    const formatter = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

    return Object.fromEntries(formatter.formatToParts(value).map((part) => [part.type, part.value]));
}

export function toInputDateTime(isoValue, timezone) {
    if (!isoValue) {
        return "";
    }

    const piece = parts(new Date(isoValue), resolveTimezone(timezone));

    return `${piece.year}-${piece.month}-${piece.day}T${piece.hour}:${piece.minute}`;
}

export function toInputDate(isoValue) {
    return isoValue ? String(isoValue).slice(0, 10) : "";
}

function offsetMinutes(value, timezone) {
    const piece = parts(value, timezone);
    const asUtc = Date.UTC(piece.year, piece.month - 1, piece.day, piece.hour, piece.minute, piece.second);

    return (asUtc - value.getTime()) / 60000;
}

export function fromInputDateTime(localValue, timezone) {
    if (!localValue) {
        return null;
    }

    const zone = resolveTimezone(timezone);
    const naive = new Date(`${localValue.slice(0, DATE_TIME_LENGTH)}:00Z`);

    // The wall clock the person typed belongs to their zone, so its offset is what turns it into UTC.
    const offset = offsetMinutes(naive, zone);
    const instant = new Date(naive.getTime() - offset * 60000);

    // A daylight saving change moves the offset itself, so it is measured again at the found instant.
    const corrected = offsetMinutes(instant, zone);

    return (corrected === offset ? instant : new Date(naive.getTime() - corrected * 60000)).toISOString();
}

export function formatDateTime(isoValue, locale, timezone) {
    if (!isoValue) {
        return "";
    }

    return new Intl.DateTimeFormat(locale, { timeZone: resolveTimezone(timezone), dateStyle: "short", timeStyle: "short" }).format(new Date(isoValue));
}

export function formatDate(isoValue, locale) {
    if (!isoValue) {
        return "";
    }

    const [year, month, day] = String(isoValue).slice(0, 10).split("-");

    return new Intl.DateTimeFormat(locale, { dateStyle: "short", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function monthName(year, month, locale) {
    return new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, 1)));
}

// Which day a week starts on where each language is read, counted the way the platform counts it: monday is 1 and sunday is 7.
export const FIRST_WEEKDAY = { en: 7, pt: 7, es: 1 };

export function weekdayNames(locale) {
    const formatter = new Intl.DateTimeFormat(locale, { weekday: "narrow", timeZone: "UTC" });

    // The seventh of january 2024 was a monday, so the offset walks the header round to the day this language begins on.
    return Array.from({ length: 7 }, (_, index) => formatter.format(new Date(Date.UTC(2024, 0, 8 + ((FIRST_WEEKDAY[locale] - 1 + index) % 7)))));
}

export function monthMatrix(year, month, locale) {
    const first = new Date(Date.UTC(year, month - 1, 1));
    const start = new Date(first);

    // The grid opens on the same day the header does, or the columns and the names above them name different days.
    start.setUTCDate(1 - ((first.getUTCDay() + 7 - (FIRST_WEEKDAY[locale] % 7)) % 7));

    return Array.from({ length: 6 }, (_, week) =>
        Array.from({ length: 7 }, (_, day) => {
            const cursor = new Date(start);
            cursor.setUTCDate(start.getUTCDate() + week * 7 + day);

            return { year: cursor.getUTCFullYear(), month: cursor.getUTCMonth() + 1, day: cursor.getUTCDate(), outside: cursor.getUTCMonth() + 1 !== month };
        }),
    );
}

export function pad(value) {
    return String(value).padStart(2, "0");
}

export function todayIn(timezone) {
    const piece = parts(new Date(), resolveTimezone(timezone));

    return { year: Number(piece.year), month: Number(piece.month), day: Number(piece.day), hour: Number(piece.hour), minute: Number(piece.minute) };
}
