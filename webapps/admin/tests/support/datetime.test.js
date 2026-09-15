import { describe, expect, it } from "vitest";

import { SUPPORTED_LOCALES } from "@/i18n";
import { FIRST_WEEKDAY, formatDate, formatDateTime, fromInputDateTime, monthMatrix, resolveTimezone, toInputDate, toInputDateTime, weekdayNames } from "@/support/datetime";

describe("datetime support", () => {
    it("falls back to the browser timezone", () => {
        expect(resolveTimezone("America/Sao_Paulo")).toBe("America/Sao_Paulo");
        expect(resolveTimezone(null)).toBeTruthy();
    });

    it("renders a utc instant in the wall clock of a zone", () => {
        expect(toInputDateTime("2026-07-29T12:30:00Z", "America/Sao_Paulo")).toBe("2026-07-29T09:30");
        expect(toInputDateTime("2026-07-29T12:30:00Z", "UTC")).toBe("2026-07-29T12:30");
    });

    it("keeps an empty instant empty", () => {
        expect(toInputDateTime(null, "UTC")).toBe("");
        expect(toInputDate(null)).toBe("");
        expect(formatDateTime(null, "en", "UTC")).toBe("");
        expect(formatDate(null, "en")).toBe("");
    });

    it("turns a wall clock back into the same utc instant", () => {
        expect(fromInputDateTime("2026-07-29T09:30", "America/Sao_Paulo")).toBe("2026-07-29T12:30:00.000Z");
        expect(fromInputDateTime("2026-07-29T12:30", "UTC")).toBe("2026-07-29T12:30:00.000Z");
    });

    it("round trips across a daylight saving change", () => {
        const instant = "2026-03-29T05:30:00.000Z";
        const wall = toInputDateTime(instant, "Europe/Lisbon");

        expect(fromInputDateTime(wall, "Europe/Lisbon")).toBe(instant);
    });

    it("answers nothing for an empty wall clock", () => {
        expect(fromInputDateTime("", "UTC")).toBeNull();
    });

    it("keeps a plain date free of any zone", () => {
        expect(toInputDate("2026-07-29")).toBe("2026-07-29");
        expect(formatDate("2026-07-29", "en")).toBe("7/29/26");
    });

    it("formats an instant for reading", () => {
        expect(formatDateTime("2026-07-29T12:30:00Z", "en", "UTC")).toContain("7/29/26");
    });

    it("says which day the week starts on for every language the panel offers", () => {
        // A calendar laid out the way another language reads it is the same mistake the editor made with spanish.
        expect(Object.keys(FIRST_WEEKDAY).sort()).toEqual([...SUPPORTED_LOCALES].sort());
    });

    it("opens the calendar on the day each language begins its week", () => {
        const opens = (locale) => {
            const cell = monthMatrix(2026, 3, locale)[0][0];

            return new Date(Date.UTC(cell.year, cell.month - 1, cell.day)).getUTCDay();
        };

        expect(opens("en")).toBe(0);
        expect(opens("pt")).toBe(0);
        expect(opens("es")).toBe(1);
    });

    it("names the columns in the order the grid draws them", () => {
        // The header and the grid read the same first day, or every column names a day other than the one under it.
        for (const locale of SUPPORTED_LOCALES) {
            const cell = monthMatrix(2026, 3, locale)[0][0];
            const opened = new Date(Date.UTC(cell.year, cell.month - 1, cell.day));

            expect(weekdayNames(locale), locale).toHaveLength(7);
            expect(weekdayNames(locale)[0], locale).toBe(new Intl.DateTimeFormat(locale, { weekday: "narrow", timeZone: "UTC" }).format(opened));
        }
    });

    it("keeps every day of the month whatever day the week starts on", () => {
        for (const locale of SUPPORTED_LOCALES) {
            for (const [year, month, days] of [
                [2026, 2, 28],
                [2024, 2, 29],
                [2026, 3, 31],
                [2026, 11, 30],
            ]) {
                const inside = monthMatrix(year, month, locale)
                    .flat()
                    .filter((cell) => !cell.outside);

                expect(inside, `${locale} ${year}-${month}`).toHaveLength(days);
            }
        }
    });
});
