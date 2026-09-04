import { countries, creditTransactions, currencies, languages, newsletterSubscriptions, outboundEmails, systemLogs, tenants, userAddresses, userBalances, users } from "./access";
import { products, purchases, userProducts } from "./commerce";
import { appEvents, banners, contentCategories, contents, externalProducts, galleries, galleryPhotos, integrations, webhookEvents } from "./content";
import { benefitGrants, benefits, entitlements, planEntitlements, plans, subscriptionBenefits, subscriptions, userEntitlements } from "./subscriptions";

// Every grid opens on the primary key, newest first, and a resource may say otherwise.
export const DEFAULT_ORDERING = "-id";

const ID_COLUMN = { name: "id", label: "field.id", type: "number" };

export const SECTIONS = ["access", "commerce", "subscriptions", "content", "integrations", "operations"];

export const RESOURCES = [
    tenants,
    users,
    userAddresses,
    languages,
    countries,
    products,
    purchases,
    userProducts,
    plans,
    entitlements,
    planEntitlements,
    benefits,
    subscriptions,
    userEntitlements,
    subscriptionBenefits,
    benefitGrants,
    contents,
    contentCategories,
    galleries,
    galleryPhotos,
    banners,
    integrations,
    externalProducts,
    webhookEvents,
    appEvents,
    systemLogs,
    outboundEmails,
    newsletterSubscriptions,
    creditTransactions,
    currencies,
    userBalances,
];

const byName = new Map(RESOURCES.map((resource) => [resource.name, resource]));

export function findResource(name) {
    return byName.get(name) || null;
}

export function resourcesOfSection(section) {
    return RESOURCES.filter((resource) => resource.section === section && !resource.managedByParent);
}

export function gridColumns(resource) {
    return [ID_COLUMN, ...resource.columns];
}

export function defaultOrdering(resource) {
    return resource.defaultOrdering || DEFAULT_ORDERING;
}

export function subitemsOf(resource) {
    return resource.subitems || [];
}

export function declaredFields(resource) {
    // A group whose fields a gateway declares carries none of its own, and what it asks for is only known at runtime.
    return (resource.groups || []).flatMap((group) => group.fields || []);
}

export function editableFields(resource) {
    return declaredFields(resource).filter((field) => !field.readOnly);
}

export function canView(resource) {
    return resource.canView !== false;
}

export function canCreate(resource) {
    return !resource.readOnly && resource.canCreate !== false;
}

export function canEdit(resource) {
    return !resource.readOnly && resource.canEdit !== false;
}

export function canDelete(resource) {
    return !resource.readOnly && resource.canDelete !== false;
}
