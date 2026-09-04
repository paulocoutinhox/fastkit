// Options are compared ignoring accents and case, with a run of digits read as a number.
export function sortByLabel(items, locale) {
    const collator = new Intl.Collator(locale, { sensitivity: "base", numeric: true });

    return [...items].sort((one, other) => collator.compare(one.label, other.label));
}
