export function text(name, label, options = {}) {
    return { name, label, type: "text", ...options };
}

export function textarea(name, label, options = {}) {
    return { name, label, type: "textarea", ...options };
}

export function html(name, label, options = {}) {
    return { name, label, type: "html", ...options };
}

export function number(name, label, options = {}) {
    return { name, label, type: "number", ...options };
}

export function decimal(name, label, options = {}) {
    return { name, label, type: "number", step: "0.01", ...options };
}

export function toggle(name, label, options = {}) {
    return { name, label, type: "switch", ...options };
}

export function choice(name, label, enumName, options = {}) {
    return { name, label, type: "select", enumName, ...options };
}

export function lookup(name, label, resource, options = {}) {
    return { name, label, type: "lookup", resource, ...options };
}

export function datetime(name, label, options = {}) {
    return { name, label, type: "datetime", ...options };
}

export function date(name, label, options = {}) {
    return { name, label, type: "date", ...options };
}

export function json(name, label, options = {}) {
    return { name, label, type: "json", ...options };
}

export function image(name, label, purpose, options = {}) {
    return { name, label, type: "image", purpose, ...options };
}

export function file(name, label, purpose, options = {}) {
    return { name, label, type: "file", purpose, ...options };
}

export function password(name, label, options = {}) {
    return { name, label, type: "password", ...options };
}

export function timezone(name, label, options = {}) {
    return { name, label, type: "timezone", ...options };
}

export function readOnly(name, label, type = "text") {
    return { name, label, type, readOnly: true };
}

export const metadata = json("meta", "field.metadata");

export const tenantField = lookup("tenantId", "field.tenant", "tenants", { hint: "field.tenantHint" });

export const auditGroup = { key: "audit", fields: [readOnly("createdAt", "field.createdAt", "datetime"), readOnly("updatedAt", "field.updatedAt", "datetime")] };
