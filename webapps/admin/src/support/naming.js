// The API speaks camelCase and a gateway declares its credential with the name of the column that keeps it.
export function camelOf(name) {
    return name.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}
