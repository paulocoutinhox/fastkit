// The API speaks camelCase and a gateway declares its credential with the name of the column that keeps it.
export function camelOf(name) {
    return name.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

// The one name a screen calls an account by, which the API already worked out from what that account actually has.
export function nameOf(user) {
    return user?.displayName || user?.username || "";
}
