// A field may hang off one or more others, declared as a name or as a list of them.
export function parentsOf(field) {
    if (!field.dependsOn) {
        return [];
    }

    return Array.isArray(field.dependsOn) ? field.dependsOn : [field.dependsOn];
}

// A level with nothing chosen above it has nothing to offer, so it waits instead of listing everything.
export function isWaiting(field, values) {
    return parentsOf(field).some((name) => values[name] === null || values[name] === undefined || values[name] === "");
}

// The parents narrow the dependent query, under the name `filterAs` gives them when it asks differently.
export function narrowingFilters(field, values) {
    const named = field.filterAs || {};

    return Object.fromEntries(parentsOf(field).map((name) => [named[name] || name, values[name]]));
}

// Changing a level empties every level below it, however deep the chain runs.
export function dependentsOf(fields, name) {
    const found = [];
    const pending = [name];

    while (pending.length) {
        const parent = pending.shift();

        fields.forEach((field) => {
            if (parentsOf(field).includes(parent) && !found.includes(field.name)) {
                found.push(field.name);
                pending.push(field.name);
            }
        });
    }

    return found;
}

// A dotted path reaches into what the API expanded, so a form may start from a relation it does not store.
export function valueAt(record, path) {
    return path.split(".").reduce((current, key) => (current === null || current === undefined ? null : current[key]), record) ?? null;
}
