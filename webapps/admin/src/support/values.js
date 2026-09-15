// What a field holds before anybody typed in it.
function initialValue(field) {
    if (field.default !== undefined) {
        return field.default;
    }

    return field.type === "json" ? {} : field.type === "switch" ? false : null;
}

export function defaults(fields) {
    return Object.fromEntries(fields.map((field) => [field.name, initialValue(field)]));
}

function loadedValue(record, field) {
    return record[field.name] ?? (field.type === "json" ? {} : null);
}

// The form and the subitem panel fill a record the same way, so editing one never behaves unlike the other.
export function pickValues(record, fields) {
    return Object.fromEntries(fields.map((field) => [field.name, loadedValue(record, field)]));
}
