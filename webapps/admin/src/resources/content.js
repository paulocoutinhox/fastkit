import { auditGroup, choice, date, datetime, decimal, html, image, lookup, metadata, number, password, readOnly, tenantField, text, textarea, toggle } from "./fields";
import { contentOnSite, webhookUrl } from "@/support/links";

export const contents = {
    name: "contents",
    ordering: ["id", "title", "tag", "publishedAt", "createdAt"],
    section: "content",
    icon: "document",
    labelField: "title",
    rowActions: [{ icon: "external", title: "action.openOnSite", href: contentOnSite }],
    columns: [
        { name: "title", label: "field.title" },
        { name: "tag", label: "field.tag", type: "code" },
        { name: "category", label: "field.category", type: "reference", referenceField: "name" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "categoryId", label: "field.category", type: "lookup", resource: "content-categories" },
        { name: "languageId", label: "field.language", type: "lookup", resource: "languages" },
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("title", "field.title", { required: true }), text("tag", "field.tag"), lookup("categoryId", "field.category", "content-categories"), lookup("languageId", "field.language", "languages"), tenantField] },
        { key: "content", fields: [html("content", "field.content")] },
        { key: "publication", fields: [date("publishedAt", "field.publishedAt"), toggle("active", "field.active", { default: true })] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
};

export const contentCategories = {
    name: "content-categories",
    ordering: ["id", "name", "tag", "createdAt"],
    section: "content",
    icon: "tag",
    labelField: "name",
    columns: [
        { name: "name", label: "field.name" },
        { name: "tag", label: "field.tag", type: "code" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [{ key: "identification", fields: [text("name", "field.name", { required: true }), text("tag", "field.tag"), tenantField, toggle("active", "field.active", { default: true })] }, auditGroup],
};

export const banners = {
    name: "banners",
    ordering: ["id", "title", "placement", "position", "startsAt", "endsAt", "createdAt"],
    section: "content",
    icon: "image",
    labelField: "title",
    columns: [
        { name: "image", label: "field.image", type: "thumbnail" },
        { name: "title", label: "field.title" },
        { name: "placement", label: "field.placement", type: "enum", enumName: "banner_placement" },
        { name: "language", label: "field.language", type: "reference", referenceField: "name" },
        { name: "views", label: "field.views", type: "number" },
        { name: "clicks", label: "field.clicks", type: "number" },
        { name: "position", label: "field.position", type: "number" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "placement", label: "field.placement", type: "enum", enumName: "banner_placement" },
        { name: "languageId", label: "field.language", type: "lookup", resource: "languages" },
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("title", "field.title", { required: true }), choice("placement", "field.placement", "banner_placement", { required: true, default: "home" }), lookup("languageId", "field.language", "languages"), text("url", "field.url"), tenantField] },
        { key: "files", fields: [image("image", "field.image", "banner")] },
        { key: "availability", fields: [number("position", "field.position", { min: 0, default: 0 }), datetime("startsAt", "field.startsAt"), datetime("endsAt", "field.endsAt"), toggle("active", "field.active", { default: true })] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
    viewExtra: [
        { name: "uuid", label: "field.uuid" },
        { name: "views", label: "field.views", type: "number" },
        { name: "clicks", label: "field.clicks", type: "number" },
    ],
};

export const integrations = {
    name: "integrations",
    ordering: ["id", "provider", "environment", "createdAt"],
    section: "integrations",
    icon: "plug",
    labelField: "provider",
    rowActions: [{ icon: "copy", title: "action.copyWebhookUrl", copy: webhookUrl }],
    columns: [
        { name: "provider", label: "field.provider", type: "enum", enumName: "provider" },
        { name: "environment", label: "field.environment", type: "enum", enumName: "environment" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "provider", label: "field.provider", type: "enum", enumName: "provider" },
        { name: "environment", label: "field.environment", type: "enum", enumName: "environment" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [lookup("tenantId", "field.tenant", "tenants", { required: true }), choice("provider", "field.provider", "provider", { required: true }), choice("environment", "field.environment", "environment", { required: true, default: "production" })] },
        { key: "credentials", fieldsFrom: "provider" },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
    viewExtra: [{ name: "webhookKey", label: "field.webhookKey", type: "code" }],
};

export const externalProducts = {
    name: "external-products",
    ordering: ["id", "externalId", "displayName", "createdAt"],
    section: "integrations",
    icon: "plug",
    labelField: "externalId",
    columns: [
        { name: "externalId", label: "field.externalId", type: "code" },
        { name: "displayName", label: "field.displayName" },
        { name: "integration", label: "field.integration", type: "reference", referenceField: "provider" },
        { name: "plan", label: "field.plan", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "integrationId", label: "field.integration", type: "lookup", resource: "integrations" },
        { name: "planId", label: "field.plan", type: "lookup", resource: "plans", dependsOn: "integrationId" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        {
            key: "identification",
            fields: [lookup("integrationId", "field.integration", "integrations", { required: true }), lookup("planId", "field.plan", "plans", { required: true, dependsOn: "integrationId", hint: "field.planHint" }), text("externalId", "field.externalId", { required: true }), text("displayName", "field.displayName")],
        },
        { key: "billing", fields: [text("referenceCurrency", "field.referenceCurrency", { max: 3 }), decimal("referencePrice", "field.referencePrice", { min: 0 })] },
        { key: "advanced", fields: [textarea("notes", "field.notes"), toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
};

export const webhookEvents = {
    name: "webhook-events",
    ordering: ["id", "action", "status", "occurredAt", "createdAt"],
    section: "integrations",
    icon: "bell",
    labelField: "externalEventId",
    readOnly: true,
    searchable: false,
    columns: [
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "action", label: "field.eventType", type: "enum", enumName: "normalized_action" },
        { name: "integration", label: "field.integration", type: "reference", referenceField: "provider" },
        { name: "status", label: "field.status", type: "enum", enumName: "webhook_event_status" },
        { name: "occurredAt", label: "field.occurredAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "integrationId", label: "field.integration", type: "lookup", resource: "integrations" },
        { name: "status", label: "field.status", type: "enum", enumName: "webhook_event_status" },
        { name: "action", label: "field.eventType", type: "enum", enumName: "normalized_action" },
    ],
    viewExtra: [
        { name: "externalEventId", label: "field.externalId", type: "code" },
        { name: "payload", label: "field.payload", type: "json" },
        { name: "payloadHash", label: "field.payloadHash", type: "code" },
        { name: "processedAt", label: "field.processedAt", type: "datetime" },
        { name: "attempts", label: "field.attempts", type: "number" },
        { name: "errorCode", label: "field.errorCode", type: "code" },
        { name: "errorMessage", label: "field.errorMessage" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
};

export const appEvents = {
    name: "app-events",
    ordering: ["id", "name", "status", "occurredAt", "createdAt"],
    section: "operations",
    icon: "bell",
    labelField: "name",
    columns: [
        { name: "name", label: "field.name", type: "code" },
        { name: "user", label: "field.user", type: "reference", referenceField: "username" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "status", label: "field.status", type: "enum", enumName: "app_event_status" },
        { name: "occurredAt", label: "field.occurredAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "status", label: "field.status", type: "enum", enumName: "app_event_status" },
    ],
    groups: [
        { key: "identification", fields: [text("uuid", "field.uuid", { required: true }), text("name", "field.name", { required: true }), tenantField, lookup("userId", "field.user", "users")] },
        { key: "delivery", fields: [datetime("occurredAt", "field.occurredAt", { required: true }), choice("status", "field.status", "app_event_status", { default: "pending" })] },
        { key: "advanced", fields: [{ name: "params", label: "field.params", type: "json" }] },
        auditGroup,
    ],
    viewExtra: [
        { name: "attempts", label: "field.attempts", type: "number" },
        { name: "errorCode", label: "field.errorCode", type: "code" },
        { name: "errorMessage", label: "field.errorMessage" },
        { name: "processedAt", label: "field.processedAt", type: "datetime" },
    ],
    readOnly: true,
};

export const galleries = {
    name: "galleries",
    ordering: ["id", "title", "tag", "position", "publishedAt", "createdAt"],
    defaultOrdering: "position",
    section: "content",
    icon: "image",
    labelField: "title",
    columns: [
        { name: "title", label: "field.title" },
        { name: "tag", label: "field.tag", type: "code" },
        { name: "language", label: "field.language", type: "reference", referenceField: "name" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "languageId", label: "field.language", type: "lookup", resource: "languages" },
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("title", "field.title", { required: true }), text("tag", "field.tag"), lookup("languageId", "field.language", "languages"), tenantField] },
        { key: "content", fields: [textarea("description", "field.description")] },
        { key: "publication", fields: [date("publishedAt", "field.publishedAt"), number("position", "field.position", { min: 0, default: 0 }), toggle("active", "field.active", { default: true })] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
    subitems: [{ resource: "gallery-photos", foreignKey: "galleryId", orderBy: "position" }],
};

export const galleryPhotos = {
    name: "gallery-photos",
    ordering: ["id", "position", "createdAt"],
    defaultOrdering: "position",
    section: "content",
    icon: "image",
    labelField: "caption",
    columns: [
        { name: "image", label: "field.image", type: "thumbnail" },
        { name: "caption", label: "field.caption" },
        { name: "position", label: "field.position", type: "number" },
    ],
    filters: [{ name: "galleryId", label: "field.gallery", type: "lookup", resource: "galleries" }],
    groups: [
        { key: "identification", fields: [lookup("galleryId", "field.gallery", "galleries", { required: true }), image("image", "field.image", "gallery-photo", { required: true })] },
        { key: "content", fields: [text("caption", "field.caption"), number("position", "field.position", { min: 0, default: 0 })] },
        auditGroup,
    ],
    managedByParent: true,
};
