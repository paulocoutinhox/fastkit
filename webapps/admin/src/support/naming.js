// The API speaks camelCase and a gateway declares its credential with the name of the column that keeps it.
export function camelOf(name) {
    return name.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

// Whether a record holds a credential is answered by a flag named after the column that keeps it, which is never read back.
export function heldFlagOf(field) {
    const name = camelOf(field);

    return `has${name.charAt(0).toUpperCase()}${name.slice(1)}`;
}

// The one name a screen calls an account by, which the API already worked out from what that account actually has.
export function nameOf(user) {
    return user?.displayName ?? "";
}
