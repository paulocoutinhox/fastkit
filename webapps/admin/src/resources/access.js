import { auditGroup, choice, html, image, json, lookup, metadata, number, password, readOnly, tenantField, text, timezone, toggle } from "./fields";

export const tenants = {
    name: "tenants",
    ordering: ["id", "code", "name", "domain", "createdAt"],
    section: "access",
    icon: "building",
    labelField: "name",
    columns: [
        { name: "code", label: "field.code", type: "code" },
        { name: "name", label: "field.name" },
        { name: "domain", label: "field.domain" },
        { name: "active", label: "field.active", type: "boolean" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [{ name: "active", label: "field.active", type: "boolean" }],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("code", "field.code"), text("domain", "field.domain", { required: true })] },
        { key: "contact", fields: [text("emailContact", "field.emailContact", { inputType: "email" }), text("emailAdministrative", "field.emailAdministrative", { inputType: "email" })] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
};

export const users = {
    name: "users",
    ordering: ["id", "username", "email", "firstName", "lastName", "role", "status", "createdAt"],
    section: "access",
    icon: "user",
    labelField: "username",
    columns: [
        { name: "username", label: "field.username", type: "code" },
        { name: "email", label: "field.email" },
        { name: "role", label: "field.role", type: "enum", enumName: "user_role" },
        { name: "reachesShared", label: "field.reachesShared", type: "boolean" },
        { name: "status", label: "field.status", type: "enum", enumName: "user_status" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [
        { name: "role", label: "field.role", type: "enum", enumName: "user_role" },
        { name: "status", label: "field.status", type: "enum", enumName: "user_status" },
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
    ],
    groups: [
        { key: "identification", fields: [text("username", "field.username"), text("firstName", "field.firstName"), text("lastName", "field.lastName"), text("nickname", "field.nickname")] },
        { key: "contact", fields: [text("email", "field.email", { inputType: "email" }), text("cpf", "field.cpf"), text("mobilePhone", "field.mobilePhone")] },
        {
            key: "access",
            fields: [
                password("password", "field.password", { requiredOnCreate: true, storedBy: "hasPassword" }),
                choice("role", "field.role", "user_role", { required: true, default: "normal" }),
                choice("status", "field.status", "user_status", { required: true, default: "active" }),
                tenantField,
                toggle("reachesShared", "field.reachesShared", { default: false }),
            ],
        },
        { key: "profile", fields: [choice("gender", "field.gender", "user_gender", { default: "none" }), image("avatar", "field.avatar", "avatar"), lookup("languageId", "field.language", "languages"), timezone("timezone", "common.timezone"), html("notes", "field.notes")] },
        { key: "identity", fields: [readOnly("token", "field.token")] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
    viewExtra: [{ name: "lastLoginAt", label: "field.lastLoginAt", type: "datetime" }],
};

export const languages = {
    name: "languages",
    ordering: ["id", "name", "codeIso6391", "createdAt"],
    section: "access",
    icon: "globe",
    labelField: "name",
    columns: [
        { name: "name", label: "field.name" },
        { name: "nativeName", label: "field.nativeName" },
        { name: "codeIso6391", label: "field.codeIso6391", type: "code" },
        { name: "codeIsoLanguage", label: "field.codeIsoLanguage", type: "code" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [{ name: "active", label: "field.active", type: "boolean" }],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("nativeName", "field.nativeName", { required: true }), text("codeIso6391", "field.codeIso6391", { required: true, max: 8 }), text("codeIsoLanguage", "field.codeIsoLanguage", { required: true, max: 16 })] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true })] },
        auditGroup,
    ],
};

export const countries = {
    name: "countries",
    ordering: ["id", "name", "codeIso31661", "createdAt"],
    defaultOrdering: "name",
    section: "access",
    icon: "globe",
    labelField: "name",
    activatable: true,
    columns: [
        { name: "name", label: "field.name" },
        { name: "codeIso31661", label: "field.codeIso31661", type: "code" },
        { name: "postalCodeProvider", label: "field.postalCodeProvider", type: "enum", enumName: "postal_code_provider" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "postalCodeProvider", label: "field.postalCodeProvider", type: "enum", enumName: "postal_code_provider" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("codeIso31661", "field.codeIso31661", { required: true, max: 2 })] },
        { key: "advanced", fields: [choice("postalCodeProvider", "field.postalCodeProvider", "postal_code_provider"), text("phoneMask", "field.phoneMask", { max: 32 }), toggle("active", "field.active", { default: true })] },
        auditGroup,
    ],
};

export const newsletterSubscriptions = {
    name: "newsletter-subscriptions",
    ordering: ["id", "email", "status", "settledAt", "createdAt"],
    section: "operations",
    icon: "document",
    labelField: "email",
    readOnly: true,
    columns: [
        { name: "email", label: "field.email" },
        { name: "status", label: "field.status", type: "enum", enumName: "newsletter_status" },
        { name: "locale", label: "field.locale", type: "code" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "status", label: "field.status", type: "enum", enumName: "newsletter_status" },
    ],
    viewExtra: [
        { name: "settledAt", label: "field.settledAt", type: "datetime" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
};

export const currencies = {
    name: "currencies",
    ordering: ["id", "code", "name", "position", "createdAt"],
    defaultOrdering: "position",
    section: "access",
    icon: "coins",
    labelField: "name",
    activatable: true,
    columns: [
        { name: "code", label: "field.code", type: "code" },
        { name: "name", label: "field.name" },
        { name: "symbol", label: "field.symbol" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true, maxLength: 128 }), text("code", "field.code", { maxLength: 32, hint: "field.codeHint" }), text("symbol", "field.symbol", { maxLength: 8 }), tenantField] },
        { key: "presentation", fields: [number("position", "field.position", { min: 0, default: 0 }), toggle("active", "field.active", { default: true })] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
};

export const userBalances = {
    name: "user-balances",
    ordering: ["id", "amount", "createdAt"],
    searchable: false,
    section: "access",
    icon: "coins",
    labelField: "id",
    readOnly: true,
    columns: [
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "currency", label: "field.currency", type: "reference", referenceField: "name" },
        { name: "amount", label: "field.amount", type: "number" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "currencyId", label: "field.currency", type: "lookup", resource: "currencies" },
    ],
    viewExtra: [
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
        { name: "updatedAt", label: "field.updatedAt", type: "datetime" },
    ],
};

export const creditTransactions = {
    name: "credit-transactions",
    ordering: ["id", "amount", "createdAt"],
    section: "access",
    icon: "coins",
    labelField: "idempotencyKey",
    canEdit: false,
    canDelete: false,
    columns: [
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "currency", label: "field.currency", type: "reference", referenceField: "name" },
        { name: "type", label: "field.type", type: "enum", enumName: "credit_transaction_type" },
        { name: "amount", label: "field.amount", type: "number" },
        { name: "balanceAfter", label: "field.balanceAfter", type: "number" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "currencyId", label: "field.currency", type: "lookup", resource: "currencies" },
        { name: "type", label: "field.type", type: "enum", enumName: "credit_transaction_type" },
    ],
    groups: [
        {
            key: "movement",
            fields: [
                lookup("userId", "field.user", "users", { required: true }),
                lookup("currencyId", "field.currency", "currencies", { required: true }),
                choice("type", "field.type", "credit_transaction_type", { required: true }),
                number("amount", "field.amount", { required: true }),
                text("description", "field.description"),
            ],
        },
        { key: "advanced", fields: [metadata] },
    ],
    viewExtra: [
        { name: "balanceAfter", label: "field.balanceAfter", type: "number" },
        { name: "idempotencyKey", label: "field.idempotencyKey", type: "code" },
        { name: "benefitGrantId", label: "field.benefitGrant", type: "number" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
};

export const systemLogs = {
    name: "system-logs",
    ordering: ["id", "level", "category", "createdAt"],
    section: "operations",
    icon: "list",
    labelField: "category",
    columns: [
        { name: "level", label: "field.level", type: "enum", enumName: "log_level" },
        { name: "category", label: "field.category", type: "enum", enumName: "log_category" },
        { name: "description", label: "field.description", type: "truncate" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [
        { name: "level", label: "field.level", type: "enum", enumName: "log_level" },
        { name: "category", label: "field.category", type: "enum", enumName: "log_category" },
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
    ],
    groups: [
        { key: "content", fields: [choice("level", "field.level", "log_level", { required: true, default: "info" }), text("category", "field.category"), { name: "description", label: "field.description", type: "textarea", required: true }] },
        { key: "identification", fields: [tenantField, lookup("userId", "field.user", "users")] },
        { key: "advanced", fields: [json("meta", "field.metadata")] },
        auditGroup,
    ],
    readOnly: true,
};

export const outboundEmails = {
    name: "outbound-emails",
    ordering: ["id", "status", "attempts", "sentAt", "createdAt"],
    section: "operations",
    icon: "document",
    labelField: "subject",
    readOnly: true,
    columns: [
        { name: "toAddress", label: "field.toAddress" },
        { name: "subject", label: "field.subject", type: "truncate" },
        { name: "template", label: "field.template", type: "code" },
        { name: "status", label: "field.status", type: "enum", enumName: "outbound_email_status" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "status", label: "field.status", type: "enum", enumName: "outbound_email_status" },
        { name: "template", label: "field.template", type: "text" },
    ],
    // The context a message was written from is never drawn, because a password reset carries its token in it.
    viewExtra: [
        { name: "locale", label: "field.locale", type: "code" },
        { name: "attempts", label: "field.attempts", type: "number" },
        { name: "sentAt", label: "field.sentAt", type: "datetime" },
        { name: "errorCode", label: "field.errorCode", type: "code" },
        { name: "errorMessage", label: "field.errorMessage" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
};

export const userAddresses = {
    name: "user-addresses",
    ordering: ["id", "type", "city", "createdAt"],
    section: "access",
    icon: "user",
    labelField: "line1",
    columns: [
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "type", label: "field.type", type: "enum", enumName: "user_address_type" },
        { name: "city", label: "field.city" },
        { name: "state", label: "field.state" },
        { name: "countryCode", label: "field.countryCode", type: "code" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "type", label: "field.type", type: "enum", enumName: "user_address_type" },
        { name: "countryCode", label: "field.countryCode", type: "text" },
    ],
    groups: [
        { key: "identification", fields: [lookup("userId", "field.user", "users", { required: true }), choice("type", "field.type", "user_address_type", { required: true, default: "main" })] },
        {
            key: "place",
            fields: [
                text("line1", "field.line1", { required: true, maxLength: 255 }),
                text("streetNumber", "field.streetNumber", { maxLength: 32 }),
                text("complement", "field.complement", { maxLength: 255 }),
                text("district", "field.district", { maxLength: 128 }),
                text("city", "field.city", { required: true, maxLength: 128 }),
                text("state", "field.state", { required: true, maxLength: 128 }),
                text("postalCode", "field.postalCode", { required: true, maxLength: 32 }),
                text("countryCode", "field.countryCode", { required: true, maxLength: 2 }),
            ],
        },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
};
