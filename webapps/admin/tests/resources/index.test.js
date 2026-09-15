import { describe, expect, it } from "vitest";

import { FIELD_COMPONENTS } from "@/components/fields/registry";
import en from "@/i18n/en";
import { DEFAULT_ORDERING, RESOURCES, SECTIONS, canCreate, canDelete, canEdit, declaredFields, defaultOrdering, editableFields, findResource, gridColumns, resourcesOfSection } from "@/resources";
import * as fields from "@/resources/fields";
import { parentsOf } from "@/support/dependencies";

const LABEL_KEYS = new Set(Object.keys(en.field).map((name) => `field.${name}`));

// What the API accepts a file through, proved against the real set by the backend guard that reads `services/upload.UPLOAD_RULES`.
const UPLOAD_PURPOSES = ["image", "avatar", "banner", "gallery-photo", "product-image", "product-file", "plan-image"];

describe("resource registry", () => {
    it("names every resource once", () => {
        const names = RESOURCES.map((resource) => resource.name);

        expect(new Set(names).size).toBe(names.length);
    });

    it("keeps every resource inside a known section", () => {
        RESOURCES.forEach((resource) => expect(SECTIONS).toContain(resource.section));
    });

    it("translates every resource in both catalogs", () => {
        RESOURCES.forEach((resource) => {
            expect(en.resource[resource.name]).toBeDefined();
            expect(en.resource[resource.name].menu).toBeDefined();
            expect(en.resource[resource.name].title).toBeDefined();
            expect(en.resource[resource.name].singular).toBeDefined();
        });
    });

    it("declares a label the delete dialog can show", () => {
        RESOURCES.forEach((resource) => expect(resource.labelField).toBeTruthy());
    });

    it("translates every column and field label", () => {
        RESOURCES.forEach((resource) => {
            const columns = [...resource.columns, ...resource.filters, ...(resource.viewExtra || [])];
            const declared = declaredFields(resource);

            [...columns, ...declared].forEach((entry) => {
                if (entry.label.startsWith("field.")) {
                    expect(LABEL_KEYS, `${resource.name}: ${entry.label}`).toContain(entry.label);
                }
            });
        });
    });

    it("translates every field group", () => {
        RESOURCES.forEach((resource) => (resource.groups || []).forEach((group) => expect(en.group[group.key], `${resource.name}: ${group.key}`).toBeDefined()));
    });

    it("points every lookup at a resource that exists", () => {
        RESOURCES.forEach((resource) => {
            const lookups = [...resource.filters, ...declaredFields(resource)].filter((entry) => entry.type === "lookup");

            lookups.forEach((entry) => expect(findResource(entry.resource), `${resource.name}: ${entry.resource}`).not.toBeNull());
        });
    });

    it("names every enum the api publishes", () => {
        RESOURCES.forEach((resource) => {
            const withEnum = [...resource.columns, ...resource.filters, ...(resource.viewExtra || []), ...declaredFields(resource)].filter((entry) => entry.enumName);

            withEnum.forEach((entry) => expect(en.enum[entry.enumName], `${resource.name}: ${entry.enumName}`).toBeDefined());
        });
    });

    it("narrows every dependent field by a sibling that exists", () => {
        RESOURCES.forEach((resource) => {
            const declared = declaredFields(resource).map((field) => field.name);
            const filters = resource.filters.map((filter) => filter.name);

            declaredFields(resource).forEach((field) => {
                parentsOf(field).forEach((parent) => expect(declared, `${resource.name}: ${field.name} depends on ${parent}`).toContain(parent));
            });

            resource.filters.forEach((filter) => {
                parentsOf(filter).forEach((parent) => expect(filters, `${resource.name} filter ${filter.name} depends on ${parent}`).toContain(parent));
            });
        });
    });

    it("uploads only through a purpose the api accepts", () => {
        const carriers = RESOURCES.flatMap(declaredFields).filter((field) => field.purpose);

        expect(carriers.length).toBeGreaterThan(0);
        carriers.forEach((field) => expect(UPLOAD_PURPOSES, `${field.name}: ${field.purpose}`).toContain(field.purpose));
    });

    it("fills every section of the menu", () => {
        SECTIONS.forEach((section) => expect(resourcesOfSection(section).length, section).toBeGreaterThan(0));
    });

    it("keeps a resource managed by its parent out of the menu and still reachable", () => {
        const managed = RESOURCES.filter((resource) => resource.managedByParent);

        expect(managed.length).toBeGreaterThan(0);

        managed.forEach((resource) => {
            expect(
                resourcesOfSection(resource.section).map((entry) => entry.name),
                resource.name,
            ).not.toContain(resource.name);
            expect(findResource(resource.name), resource.name).not.toBeNull();
        });
    });

    it("keeps out of the menu only what a parent manages or the engine writes", () => {
        const owned = RESOURCES.flatMap((resource) => (resource.subitems || []).map((subitem) => subitem.resource));

        RESOURCES.filter((resource) => resource.managedByParent).forEach((resource) => {
            expect(owned.includes(resource.name) || resource.readOnly === true, resource.name).toBe(true);
        });
    });

    it("leads every grid with the primary key", () => {
        RESOURCES.forEach((resource) => {
            const columns = gridColumns(resource);

            expect(columns[0].name).toBe("id");
            expect(columns.length).toBe(resource.columns.length + 1);
        });
    });

    it("orders every grid by the newest primary key unless the resource says otherwise", () => {
        expect(DEFAULT_ORDERING).toBe("-id");
        expect(defaultOrdering(findResource("tenants"))).toBe("-id");
        expect(defaultOrdering({ defaultOrdering: "position" })).toBe("position");
    });

    it("keeps the menu name short inside a section that already names the family", () => {
        const commerce = RESOURCES.filter((resource) => resource.section === "commerce");

        expect(commerce.length).toBeGreaterThan(1);
        commerce.filter((resource) => resource.name !== "products").forEach((resource) => expect(en.resource[resource.name].menu, resource.name).not.toContain("Commerce"));
    });

    it("writes every english label in title case", () => {
        Object.entries(en.resource).forEach(([name, labels]) => {
            Object.entries(labels).forEach(([kind, label]) => {
                label.split(" ").forEach((word) => expect(word[0], `${name}.${kind}: ${label}`).toBe(word[0].toUpperCase()));
            });
        });
    });

    it("hangs every subitem off a resource that exists and a filter the api accepts", () => {
        const owners = RESOURCES.filter((resource) => (resource.subitems || []).length);

        expect(owners.length).toBeGreaterThan(0);

        owners.forEach((owner) =>
            owner.subitems.forEach((subitem) => {
                const child = findResource(subitem.resource);

                expect(child, `${owner.name}: ${subitem.resource}`).not.toBeNull();
                expect(
                    editableFields(child).map((field) => field.name),
                    `${owner.name}: ${subitem.foreignKey}`,
                ).toContain(subitem.foreignKey);
            }),
        );
    });

    it("answers nothing for an unknown resource", () => {
        expect(findResource("nothing")).toBeNull();
    });

    it("groups the resources of a section", () => {
        expect(resourcesOfSection("access").map((resource) => resource.name)).toContain("users");
        expect(resourcesOfSection("nothing")).toEqual([]);
    });

    it("lists only the writable fields of a resource", () => {
        const names = editableFields(findResource("tenants")).map((field) => field.name);

        expect(names).toContain("name");
        expect(names).not.toContain("createdAt");
    });

    it("closes the write path of a read only resource", () => {
        const readOnly = findResource("benefit-grants");

        expect(canCreate(readOnly)).toBe(false);
        expect(canEdit(readOnly)).toBe(false);
        expect(canDelete(readOnly)).toBe(false);
    });

    it("keeps the ledger append only", () => {
        const ledger = findResource("credit-transactions");

        expect(canCreate(ledger)).toBe(true);
        expect(canEdit(ledger)).toBe(false);
        expect(canDelete(ledger)).toBe(false);
    });

    it("opens the write path of an ordinary resource", () => {
        const tenants = findResource("tenants");

        expect(canCreate(tenants)).toBe(true);
        expect(canEdit(tenants)).toBe(true);
        expect(canDelete(tenants)).toBe(true);
    });
});

describe("field builders", () => {
    it("gives every type a resource declares a component and a builder of its own", () => {
        // The type is a closed set, so one nobody wrote a component for draws a field with nothing inside it.
        const built = new Set(
            Object.values(fields)
                .filter((entry) => typeof entry === "function")
                .map((builder) => builder("probe", "field.probe", "probe").type),
        );

        for (const type of new Set(RESOURCES.flatMap(declaredFields).map((field) => field.type))) {
            expect(FIELD_COMPONENTS[type], type).toBeTruthy();
            expect(built.has(type), type).toBe(true);
        }
    });

    it("builds one descriptor per data type", () => {
        expect(fields.text("code", "field.code")).toEqual({ name: "code", label: "field.code", type: "text" });
        expect(fields.textarea("notes", "field.notes").type).toBe("textarea");
        expect(fields.html("body", "field.content").type).toBe("html");
        expect(fields.number("position", "field.position").type).toBe("number");
        expect(fields.decimal("price", "field.price").step).toBe("0.01");
        expect(fields.toggle("active", "field.active").type).toBe("switch");
        expect(fields.choice("role", "field.role", "user_role").enumName).toBe("user_role");
        expect(fields.lookup("tenantId", "field.tenant", "tenants").resource).toBe("tenants");
        expect(fields.datetime("startsAt", "field.startsAt").type).toBe("datetime");
        expect(fields.date("published_at", "field.publishedAt").type).toBe("date");
        expect(fields.json("meta", "field.metadata").type).toBe("json");
        expect(fields.image("image", "field.image", "product-image").purpose).toBe("product-image");
        expect(fields.file("file", "field.file", "product-file").purpose).toBe("product-file");
        expect(fields.password("secret", "field.secret").type).toBe("password");
        expect(fields.readOnly("createdAt", "field.createdAt", "datetime")).toEqual({ name: "createdAt", label: "field.createdAt", type: "datetime", readOnly: true });
    });

    it("carries the shared descriptors", () => {
        expect(fields.metadata.name).toBe("meta");
        expect(fields.tenantField.resource).toBe("tenants");
        expect(fields.auditGroup.fields.every((field) => field.readOnly)).toBe(true);
    });
});

describe("a field that keeps a secret", () => {
    it("says which flag of the record tells that one is stored", () => {
        const secrets = RESOURCES.flatMap(declaredFields).filter((field) => field.type === "password");

        expect(secrets.length).toBeGreaterThan(0);

        secrets.forEach((field) => expect(field.storedBy, `${field.name} never says whether it already holds one`).toBeTruthy());
    });
});

describe("filter bar", () => {
    // The bar draws a yes/no select for anything it does not know, so a filter with no type asked the API for "true".
    const KNOWN = ["enum", "lookup", "text", "boolean"];

    it("every filter a grid draws carries a type the bar knows", () => {
        RESOURCES.forEach((resource) =>
            resource.filters.forEach((filter) => {
                expect(KNOWN, `${resource.name}: ${filter.name}`).toContain(filter.type);
            }),
        );
    });
});
