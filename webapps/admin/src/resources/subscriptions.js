import { auditGroup, choice, datetime, decimal, html, image, lookup, metadata, number, tenantField, text, toggle } from "./fields";

export const plans = {
    name: "plans",
    ordering: ["id", "code", "name", "price", "position", "createdAt"],
    defaultOrdering: "position",
    section: "subscriptions",
    icon: "card",
    labelField: "name",
    columns: [
        { name: "name", label: "field.name" },
        { name: "code", label: "field.code", type: "code" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "language", label: "field.language", type: "reference", referenceField: "name" },
        { name: "currency", label: "field.currency" },
        { name: "price", label: "field.price", type: "number" },
        { name: "featured", label: "field.featured", type: "boolean" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "languageId", label: "field.language", type: "lookup", resource: "languages" },
        { name: "featured", label: "field.featured", type: "boolean" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("code", "field.code"), lookup("tenantId", "field.tenant", "tenants", { required: true }), lookup("languageId", "field.language", "languages"), image("image", "field.image", "plan-image")] },
        { key: "content", fields: [html("description", "field.description")] },
        { key: "pricing", fields: [text("currency", "field.currency", { required: true, default: "USD" }), decimal("price", "field.price", { min: 0, default: 0 })] },
        { key: "billing", fields: [choice("billingIntervalUnit", "field.billingIntervalUnit", "interval_unit"), number("billingIntervalValue", "field.billingIntervalValue", { min: 1 })] },
        {
            key: "policies",
            fields: [
                choice("resumeDeliveryPolicy", "field.resumeDeliveryPolicy", "resume_delivery_policy", { required: true, default: "same_cycle" }),
                choice("trialBenefitPolicy", "field.trialBenefitPolicy", "benefit_policy", { default: "access_only" }),
                choice("graceBenefitPolicy", "field.graceBenefitPolicy", "benefit_policy", { default: "access_only" }),
            ],
        },
        { key: "presentation", fields: [toggle("featured", "field.featured"), number("position", "field.position", { min: 0, default: 0 })] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
    subitems: [{ resource: "plan-entitlements", foreignKey: "planId" }],
};

export const entitlements = {
    name: "entitlements",
    ordering: ["id", "name", "createdAt"],
    section: "subscriptions",
    icon: "key",
    labelField: "name",
    columns: [
        { name: "name", label: "field.name" },
        { name: "code", label: "field.code", type: "code" },
        { name: "tenant", label: "field.tenant", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        { key: "identification", fields: [text("name", "field.name", { required: true }), text("code", "field.code", { required: true }), tenantField] },
        { key: "content", fields: [html("description", "field.description")] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
    subitems: [{ resource: "benefits", foreignKey: "entitlementId" }],
};

export const planEntitlements = {
    name: "plan-entitlements",
    searchable: false,
    ordering: ["id", "createdAt"],
    section: "subscriptions",
    icon: "key",
    labelField: "id",
    columns: [
        { name: "plan", label: "field.plan", type: "reference", referenceField: "name" },
        { name: "entitlement", label: "field.entitlement", type: "reference", referenceField: "name" },
    ],
    filters: [
        { name: "planId", label: "field.plan", type: "lookup", resource: "plans" },
        { name: "entitlementId", label: "field.entitlement", type: "lookup", resource: "entitlements" },
    ],
    groups: [{ key: "identification", fields: [lookup("planId", "field.plan", "plans", { required: true }), lookup("entitlementId", "field.entitlement", "entitlements", { required: true })] }, { key: "advanced", fields: [metadata] }, auditGroup],
    managedByParent: true,
};

export const benefits = {
    name: "benefits",
    ordering: ["id", "type", "createdAt"],
    section: "subscriptions",
    icon: "gift",
    labelField: "target",
    columns: [
        { name: "target", label: "field.target", type: "code" },
        { name: "entitlement", label: "field.entitlement", type: "reference", referenceField: "name" },
        { name: "type", label: "field.type", type: "enum", enumName: "benefit_type" },
        { name: "cadence", label: "field.cadence", type: "enum", enumName: "benefit_cadence" },
        { name: "quantity", label: "field.quantity", type: "number" },
        { name: "product", label: "field.product", type: "reference", referenceField: "name" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    filters: [
        { name: "entitlementId", label: "field.entitlement", type: "lookup", resource: "entitlements" },
        { name: "productId", label: "field.product", type: "lookup", resource: "products" },
        { name: "type", label: "field.type", type: "enum", enumName: "benefit_type" },
        { name: "cadence", label: "field.cadence", type: "enum", enumName: "benefit_cadence" },
        { name: "active", label: "field.active", type: "boolean" },
    ],
    groups: [
        {
            key: "identification",
            fields: [
                lookup("entitlementId", "field.entitlement", "entitlements", { required: true }),
                choice("type", "field.type", "benefit_type", { required: true }),
                text("target", "field.target", { required: true, hint: "field.targetHint" }),
                number("quantity", "field.quantity", { min: 1, default: 1, hint: "field.quantityHint" }),
                lookup("productId", "field.product", "products", { dependsOn: "entitlementId", hint: "field.productHint" }),
            ],
        },
        { key: "schedule", fields: [choice("cadence", "field.cadence", "benefit_cadence", { required: true }), choice("intervalUnit", "field.intervalUnit", "interval_unit"), number("intervalValue", "field.intervalValue", { min: 1 })] },
        { key: "policies", fields: [toggle("grantOnActivation", "field.grantOnActivation", { default: true }), choice("missedCyclePolicy", "field.missedCyclePolicy", "missed_cycle_policy", { default: "skip" })] },
        { key: "advanced", fields: [toggle("active", "field.active", { default: true }), metadata] },
        auditGroup,
    ],
    managedByParent: true,
};

export const subscriptions = {
    name: "subscriptions",
    ordering: ["id", "status", "startedAt", "currentPeriodEndsAt", "createdAt"],
    section: "subscriptions",
    icon: "refresh",
    labelField: "id",
    readOnly: true,
    activatable: true,
    columns: [
        { name: "user", label: "field.user", type: "reference", referenceField: "displayName" },
        { name: "plan", label: "field.plan", type: "reference", referenceField: "name" },
        { name: "status", label: "field.status", type: "enum", enumName: "subscription_status" },
        { name: "benefitStatus", label: "field.benefitStatus", type: "enum", enumName: "benefit_status" },
        { name: "currentPeriodEndsAt", label: "field.currentPeriodEndsAt", type: "datetime" },
    ],
    filters: [
        { name: "tenantId", label: "field.tenant", type: "lookup", resource: "tenants" },
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "planId", label: "field.plan", type: "lookup", resource: "plans" },
        { name: "status", label: "field.status", type: "enum", enumName: "subscription_status" },
        { name: "benefitStatus", label: "field.benefitStatus", type: "enum", enumName: "benefit_status" },
    ],
    groups: [
        { key: "identification", fields: [lookup("tenantId", "field.tenant", "tenants", { required: true }), lookup("userId", "field.user", "users", { required: true }), lookup("planId", "field.plan", "plans", { required: true })] },
        { key: "credentials", fields: [lookup("integrationId", "field.integration", "integrations"), lookup("externalProductId", "field.externalProduct", "external-products"), text("externalId", "field.externalId"), choice("environment", "field.environment", "environment")] },
        {
            key: "lifecycle",
            fields: [
                choice("status", "field.status", "subscription_status", { required: true, default: "pending" }),
                choice("benefitStatus", "field.benefitStatus", "benefit_status", { required: true, default: "active" }),
                datetime("startedAt", "field.startedAt"),
                datetime("currentPeriodStartedAt", "field.currentPeriodStartedAt"),
                datetime("currentPeriodEndsAt", "field.currentPeriodEndsAt"),
                datetime("accessUntil", "field.accessUntil"),
            ],
        },
        { key: "availability", fields: [datetime("trialEndsAt", "field.trialEndsAt"), datetime("graceUntil", "field.graceUntil"), toggle("cancelAtPeriodEnd", "field.cancelAtPeriodEnd"), datetime("canceledAt", "field.canceledAt"), datetime("expiredAt", "field.expiredAt")] },
        { key: "advanced", fields: [metadata] },
        auditGroup,
    ],
};

export const userEntitlements = {
    name: "user-entitlements",
    searchable: false,
    ordering: ["id", "status", "expiresAt", "createdAt"],
    section: "subscriptions",
    icon: "key",
    labelField: "id",
    readOnly: true,
    columns: [
        { name: "subscription", label: "field.user", type: "reference", referenceField: "user.displayName" },
        { name: "entitlement", label: "field.entitlement", type: "reference", referenceField: "name" },
        { name: "status", label: "field.status", type: "enum", enumName: "user_entitlement_status" },
        { name: "expiresAt", label: "field.expiresAt", type: "datetime" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "entitlementId", label: "field.entitlement", type: "lookup", resource: "entitlements" },
        { name: "status", label: "field.status", type: "enum", enumName: "user_entitlement_status" },
    ],
    viewExtra: [
        { name: "startedAt", label: "field.startedAt", type: "datetime" },
        { name: "meta", label: "field.metadata", type: "json" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
        { name: "updatedAt", label: "field.updatedAt", type: "datetime" },
    ],
};

export const subscriptionBenefits = {
    name: "subscription-benefits",
    ordering: ["id", "nextGrantAt", "lastGrantAt", "createdAt"],
    section: "subscriptions",
    icon: "gift",
    labelField: "target",
    readOnly: true,
    columns: [
        { name: "subscription", label: "field.user", type: "reference", referenceField: "user.displayName" },
        { name: "target", label: "field.target", type: "code" },
        { name: "benefitType", label: "field.benefitType", type: "enum", enumName: "benefit_type" },
        { name: "status", label: "field.status", type: "enum", enumName: "benefit_status" },
        { name: "nextGrantAt", label: "field.nextGrantAt", type: "datetime" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "status", label: "field.status", type: "enum", enumName: "benefit_status" },
        { name: "benefitType", label: "field.benefitType", type: "enum", enumName: "benefit_type" },
    ],
    viewExtra: [
        { name: "quantity", label: "field.quantity", type: "number" },
        { name: "product", label: "field.product", type: "reference", referenceField: "name" },
        { name: "cadence", label: "field.cadence", type: "enum", enumName: "benefit_cadence" },
        { name: "intervalUnit", label: "field.intervalUnit", type: "enum", enumName: "interval_unit" },
        { name: "intervalValue", label: "field.intervalValue", type: "number" },
        { name: "grantOnActivation", label: "field.grantOnActivation", type: "boolean" },
        { name: "missedCyclePolicy", label: "field.missedCyclePolicy", type: "enum", enumName: "missed_cycle_policy" },
        { name: "anchorAt", label: "field.anchorAt", type: "datetime" },
        { name: "lastGrantAt", label: "field.lastGrantAt", type: "datetime" },
        { name: "meta", label: "field.metadata", type: "json" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    managedByParent: true,
};

export const benefitGrants = {
    name: "benefit-grants",
    ordering: ["id", "scheduledAt", "status", "createdAt"],
    section: "subscriptions",
    icon: "gift",
    labelField: "grantKey",
    readOnly: true,
    columns: [
        { name: "grantKey", label: "field.grantKey", type: "code" },
        { name: "status", label: "field.status", type: "enum", enumName: "benefit_grant_status" },
        { name: "grantedQuantity", label: "field.grantedQuantity", type: "number" },
        { name: "scheduledAt", label: "field.scheduledAt", type: "datetime" },
    ],
    filters: [
        { name: "userId", label: "field.user", type: "lookup", resource: "users" },
        { name: "status", label: "field.status", type: "enum", enumName: "benefit_grant_status" },
    ],
    viewExtra: [
        { name: "cycleKey", label: "field.cycleKey", type: "code" },
        { name: "requestedQuantity", label: "field.requestedQuantity", type: "number" },
        { name: "result", label: "field.result", type: "json" },
        { name: "errorCode", label: "field.errorCode", type: "code" },
        { name: "errorMessage", label: "field.errorMessage" },
        { name: "attempts", label: "field.attempts", type: "number" },
        { name: "startedAt", label: "field.startedAt", type: "datetime" },
        { name: "completedAt", label: "field.completedAt", type: "datetime" },
        { name: "createdAt", label: "field.createdAt", type: "datetime" },
    ],
    managedByParent: true,
};
