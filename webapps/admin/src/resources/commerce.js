import { auditGroup, choice, decimal, file, html, image, lookup, metadata, number, tenantField, text, toggle } from "./fields";

export const products = {
    name: "products",
    ordering: ["id", "name", "slug", "price", "position", "createdAt"],
    defaultOrdering: "position",
    section: "commerce",
    icon: "tag",
    labelField: "name",
    columns: [
        { name: "image", label: "field.image", type: "thumbnail" },
        { name: "name", label: "field.name" },
        { name: "slug", label: "field.slug", type: "code" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "price", label: "field.price", type: "number" },
        { name: "credits", label: "field.credits", type: "number" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "featured", label: "field.featured", type: "boolean" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("slug", "field.slug"), tenantField] },
        { key: "content", fields: [html("description", "field.description"), image("image", "field.image", "product-image"), file("file", "field.file", "product-file", { hint: "field.productFileHint" })] },
        { key: "pricing", fields: [text("currency", "field.currency", { required: true, default: "USD" }), decimal("price", "field.price", { min: 0, default: 0 })] },
        { key: "credits", fields: [number("credits", "field.credits", { min: 0, default: 0, hint: "field.creditsHint" }), lookup("creditsCurrencyId", "field.currency", "currencies")] },
        { key: "presentation", fields: [toggle("featured", "field.featured"), number("position", "field.position", { min: 0, default: 0 })] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
};

export const purchases = {
    name: "purchases",
    ordering: ["id", "status", "price", "paidAt", "createdAt"],
    section: "commerce",
    icon: "card",
    labelField: "reference",
    readOnly: true,
    columns: [
        { name: "reference", label: "field.reference", type: "code" },
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "product", label: "field.product", type: "reference", referenceField: "name" },
        { name: "price", label: "field.price", type: "number" },
        { name: "status", label: "field.status", type: "enum", enumName: "purchase_status" },
        { name: "paidAt", label: "field.paidAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "productId", label: "field.product", type: "lookup", resource: "products" },
        { name: "integrationId", label: "field.integration", type: "lookup", resource: "integrations" },
        { name: "status", label: "field.status", type: "enum", enumName: "purchase_status" },
    ],
    viewExtra: [
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "externalId", label: "field.externalId", type: "code" },
        { name: "currency", label: "field.currency", type: "code" },
        { name: "meta", label: "field.metadata", type: "json" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
        { name: "updatedAt", label: "field.updatedAt", type: "datetime" },
    ],
};

export const userProducts = {
    name: "user-products",
    searchable: false,
    ordering: ["id", "grantedAt", "createdAt"],
    section: "commerce",
    icon: "gift",
    labelField: "id",
    readOnly: true,
    columns: [
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "product", label: "field.product", type: "reference", referenceField: "name" },
        { name: "grantedAt", label: "field.grantedAt", type: "datetime" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "productId", label: "field.product", type: "lookup", resource: "products" },
        { name: "subscriptionId", label: "field.subscription", type: "lookup", resource: "subscriptions" },
    ],
    viewExtra: [
        { name: "purchaseId", label: "field.purchase", type: "number" },
        { name: "subscriptionId", label: "field.subscription", type: "number" },
        { name: "benefitGrantId", label: "field.benefitGrant", type: "number" },
        { name: "meta", label: "field.metadata", type: "json" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
};
