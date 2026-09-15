import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import AppAlert from "@/components/ui/AppAlert.vue";
import AppBadge from "@/components/ui/AppBadge.vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppCard from "@/components/ui/AppCard.vue";
import AppIcon from "@/components/ui/AppIcon.vue";
import AppModal from "@/components/ui/AppModal.vue";
import AppPagination from "@/components/ui/AppPagination.vue";
import DataGrid from "@/components/ui/DataGrid.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ToastStack from "@/components/ui/ToastStack.vue";
import ValueDisplay from "@/components/ui/ValueDisplay.vue";
import { useMetaStore } from "@/stores/meta";
import { useUiStore } from "@/stores/ui";
import { contentOnSite, webhookUrl } from "@/support/links";
import { flushPromises, mount } from "@vue/test-utils";

describe("AppIcon", () => {
    it("draws the requested glyph", () => {
        expect(
            mount(AppIcon, { props: { name: "user" } })
                .find("path")
                .attributes("d"),
        ).toContain("M20 21v-2");
    });

    it("draws no glyph for a name nobody declared, so the mistake is seen", () => {
        expect(
            mount(AppIcon, { props: { name: "nothing" } })
                .find("path")
                .attributes("d"),
        ).toBeUndefined();
    });
});

describe("AppButton", () => {
    it("renders its label and emits a click", async () => {
        const wrapper = mount(AppButton, { slots: { default: "Save" } });

        await wrapper.trigger("click");

        expect(wrapper.text()).toBe("Save");
        expect(wrapper.emitted("click")).toHaveLength(1);
    });

    it("shows a spinner instead of the icon while loading", () => {
        const wrapper = mount(AppButton, { props: { icon: "check", loading: true } });

        expect(wrapper.find("svg").exists()).toBe(false);
        expect(wrapper.find(".animate-spin").exists()).toBe(true);
        expect(wrapper.attributes("disabled")).toBeDefined();
    });

    it("styles each variant and size", () => {
        expect(
            mount(AppButton, { props: { variant: "danger", size: "sm" } })
                .classes()
                .join(" "),
        ).toContain("bg-danger-fill");
        expect(
            mount(AppButton, { props: { variant: "secondary", size: "lg" } })
                .classes()
                .join(" "),
        ).toContain("ring-line-strong");
        expect(
            mount(AppButton, { props: { variant: "ghost" } })
                .classes()
                .join(" "),
        ).toContain("hover:bg-sunken");
    });

    it("refuses a click when disabled", () => {
        expect(mount(AppButton, { props: { disabled: true } }).attributes("disabled")).toBeDefined();
    });
});

describe("AppAlert", () => {
    it("renders the tone and the message", () => {
        const wrapper = mount(AppAlert, { props: { tone: "error", title: "Failed" }, slots: { default: "Try again" } });

        expect(wrapper.classes().join(" ")).toContain("bg-danger-soft");
        expect(wrapper.text()).toContain("Failed");
        expect(wrapper.text()).toContain("Try again");
    });

    it("draws a tone nobody declared as no tone at all, so it is seen instead of passing for one that works", () => {
        expect(
            mount(AppAlert, { props: { tone: "unknown" } })
                .classes()
                .join(" "),
        ).not.toContain("bg-sky-50");
    });
});

describe("AppBadge", () => {
    it("styles the known tones, and draws an unknown one as none", () => {
        expect(
            mount(AppBadge, { props: { tone: "success" } })
                .classes()
                .join(" "),
        ).toContain("bg-good-soft");
        expect(
            mount(AppBadge, { props: { tone: "whatever" } })
                .classes()
                .join(" "),
        ).not.toContain("bg-");
    });
});

describe("AppCard", () => {
    it("renders a header only when it has one", () => {
        expect(mount(AppCard, { props: { title: "Access", description: "Who reaches what" } }).text()).toContain("Who reaches what");
        expect(
            mount(AppCard, { slots: { default: "body" } })
                .find("header")
                .exists(),
        ).toBe(false);
    });
});

describe("EmptyState", () => {
    it("renders the message", () => {
        expect(mount(EmptyState, { props: { message: "Nothing here" } }).text()).toContain("Nothing here");
    });
});

describe("AppModal", () => {
    it("closes on escape once it is open", async () => {
        const wrapper = mount(AppModal, { props: { open: false } });

        await wrapper.setProps({ open: true });

        window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
        await nextTick();

        expect(wrapper.emitted("close")).toHaveLength(1);

        await wrapper.setProps({ open: false });

        window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
        await nextTick();

        expect(wrapper.emitted("close")).toHaveLength(1);

        wrapper.unmount();
    });

    it("stays out of the document while closed", () => {
        expect(
            mount(AppModal, { props: { open: false } })
                .find("[role=dialog]")
                .exists(),
        ).toBe(false);
    });

    it("closes on the backdrop and on the button", async () => {
        const wrapper = mount(AppModal, { props: { open: true, title: "Delete?" } });

        await wrapper.find("[role=dialog] button").trigger("click");
        expect(wrapper.emitted("close")).toHaveLength(1);

        await wrapper.find("[role=dialog]").trigger("click");
        expect(wrapper.emitted("close")).toHaveLength(2);

        window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
        await nextTick();
        expect(wrapper.emitted("close")).toHaveLength(2);

        wrapper.unmount();
    });
});

describe("AppPagination", () => {
    it("walks the pages", async () => {
        const wrapper = mount(AppPagination, { props: { count: 60, limit: 25, offset: 25 } });

        expect(wrapper.text()).toContain("Page 2 of 3");

        const [previous, next] = wrapper.findAll("button");

        await previous.trigger("click");
        await next.trigger("click");

        expect(wrapper.emitted("change")).toEqual([[0], [50]]);
    });

    it("stops at both ends", () => {
        const first = mount(AppPagination, { props: { count: 60, limit: 25, offset: 0 } });
        const last = mount(AppPagination, { props: { count: 60, limit: 25, offset: 50 } });

        expect(first.findAll("button")[0].attributes("disabled")).toBeDefined();
        expect(last.findAll("button")[1].attributes("disabled")).toBeDefined();
    });
});

describe("ToastStack", () => {
    it("renders and dismisses what the store holds", async () => {
        vi.useFakeTimers();

        const wrapper = mount(ToastStack);
        const ui = useUiStore();

        ui.success("saved");
        await nextTick();

        expect(wrapper.text()).toContain("saved");

        await wrapper.find("button").trigger("click");

        expect(ui.toasts).toHaveLength(0);

        vi.useRealTimers();
    });
});

function displayOf(column, record) {
    return mount(ValueDisplay, { props: { column, record } });
}

describe("ValueDisplay", () => {
    it("marks an empty value", () => {
        expect(displayOf({ name: "name" }, { name: null }).text()).toBe("—");
        expect(displayOf({ name: "name" }, { name: "" }).text()).toBe("—");
    });

    it("draws what a row links to before what it does to the row", () => {
        // The eye, the pencil and the trash act on the record; a link leaves for somewhere else, and comes first.
        const wrapper = mount(DataGrid, {
            props: {
                columns: [{ name: "title", label: "field.title" }],
                records: [{ id: 1, title: "Termos", tag: "termos", tenant: { code: "storycloud" }, language: { codeIso6391: "pt" } }],
                emptyMessage: "vazio",
                actions: [{ icon: "external", title: "action.openOnSite", href: contentOnSite }],
            },
        });

        const link = wrapper.find("tbody a[target='_blank']");

        expect(link.attributes("href")).toBe("/content/termos");
        expect(link.attributes("rel")).toBe("noopener");
    });

    it("draws no link where the record has no address", () => {
        // A content nobody gave a tag to is one the site answers nowhere, so there is nothing to point at.
        const wrapper = mount(DataGrid, {
            props: {
                columns: [{ name: "title", label: "field.title" }],
                records: [{ id: 1, title: "Termos", tag: "", tenant: null }],
                emptyMessage: "vazio",
                actions: [{ icon: "external", title: "action.openOnSite", href: contentOnSite }],
            },
        });

        expect(wrapper.find("tbody a[target='_blank']").exists()).toBe(false);
    });

    it("hands over what a row carries instead of leaving for it", async () => {
        // An address a provider has to be told is copied, not opened: there is nothing on the other side to visit.
        const written = [];

        vi.stubGlobal("navigator", { clipboard: { writeText: async (value) => written.push(value) } });

        const wrapper = mount(DataGrid, {
            props: {
                columns: [{ name: "provider", label: "field.provider" }],
                records: [{ id: 1, provider: "revenuecat", webhookKey: "chave-1" }],
                canView: false,
                canEdit: false,
                canDelete: false,
                emptyMessage: "vazio",
                actions: [{ icon: "copy", title: "action.copyWebhookUrl", copy: webhookUrl }],
            },
        });

        await wrapper.find("tbody button").trigger("click");
        await flushPromises();

        expect(written).toEqual([`${window.location.origin}/api/webhooks/chave-1`]);
    });

    it("draws no copy where the record has nothing to hand over", () => {
        const wrapper = mount(DataGrid, {
            props: {
                columns: [{ name: "provider", label: "field.provider" }],
                records: [{ id: 1, provider: "revenuecat", webhookKey: null }],
                canView: false,
                canEdit: false,
                canDelete: false,
                emptyMessage: "vazio",
                actions: [{ icon: "copy", title: "action.copyWebhookUrl", copy: webhookUrl }],
            },
        });

        expect(wrapper.find("tbody button").exists()).toBe(false);
    });

    it("renders a boolean with words", () => {
        expect(displayOf({ name: "active", type: "boolean" }, { active: true }).text()).toBe("Yes");
        expect(displayOf({ name: "active", type: "boolean" }, { active: false }).text()).toBe("No");
    });

    it("translates an enum and tones it", () => {
        const wrapper = displayOf({ name: "status", type: "enum", enumName: "user_status" }, { status: "blocked" });

        expect(wrapper.text()).toBe("Blocked");
        expect(wrapper.html()).toContain("bg-danger-soft");
    });

    it("keeps an unknown enum value readable", () => {
        expect(displayOf({ name: "status", type: "enum", enumName: "user_status" }, { status: "whatever" }).text()).toBe("whatever");
    });

    it("renders the remaining types", () => {
        expect(displayOf({ name: "createdAt", type: "datetime" }, { createdAt: "2026-07-29T12:00:00Z" }).text()).toContain("7/29/26");
        expect(displayOf({ name: "published_at", type: "date" }, { published_at: "2026-07-29" }).text()).toBe("7/29/26");
        expect(displayOf({ name: "position", type: "number" }, { position: 3 }).text()).toBe("3");
        expect(displayOf({ name: "code", type: "code" }, { code: "acme" }).find("code").text()).toBe("acme");
        expect(displayOf({ name: "meta", type: "json" }, { meta: { a: 1 } }).text()).toContain('"a": 1');
        expect(displayOf({ name: "description", type: "truncate" }, { description: "long text" }).text()).toBe("long text");
    });

    it("previews an html body where a script of it reaches nothing", () => {
        // An editor writes the body and an administrator reads it in a panel holding their token, so the preview is sandboxed and never inlined.
        const frame = displayOf({ name: "content", label: "field.content", type: "html" }, { content: "<img src=x onerror=steal()>" }).find("iframe");

        expect(frame.exists()).toBe(true);
        expect(frame.attributes("sandbox")).toBe("");
        expect(frame.attributes("srcdoc")).toContain("onerror=steal()");
    });

    it("renders a reference as plain text", () => {
        expect(displayOf({ name: "tenant", type: "reference", referenceField: "name" }, { tenant: { id: 2, name: "Acme" } }).text()).toBe("Acme");
    });

    it("falls back to whatever names the related record", () => {
        expect(displayOf({ name: "gallery", type: "reference", referenceField: "missing" }, { gallery: { id: 5, title: "Reception" } }).text()).toBe("Reception");
        expect(displayOf({ name: "gallery", type: "reference", referenceField: "missing" }, { gallery: { id: 5 } }).text()).toBe("#5");
    });

    it("builds media urls from the configured base", () => {
        const meta = useMetaStore();
        meta.storageBaseUrl = "/media";

        expect(displayOf({ name: "cover", type: "thumbnail", label: "Cover" }, { cover: "images/one.png" }).find("img").attributes("src")).toBe("/media/images/one.png");
        expect(displayOf({ name: "asset", type: "file" }, { asset: "files/book.epub" }).find("a").attributes("href")).toBe("/media/files/book.epub");
        expect(displayOf({ name: "asset", type: "file" }, { asset: "files/book.epub" }).text()).toBe("book.epub");
    });
});

const COLUMNS = [
    { name: "code", label: "field.code", type: "code" },
    { name: "name", label: "field.name" },
];

const RECORDS = [
    { id: 1, code: "acme", name: "Acme" },
    { id: 2, code: "blue", name: "Blue" },
];

describe("DataGrid", () => {
    it("shows the loading state", () => {
        expect(mount(DataGrid, { props: { columns: COLUMNS, records: [], loading: true, emptyMessage: "empty" } }).text()).toContain("Loading");
    });

    it("shows the empty state", () => {
        expect(mount(DataGrid, { props: { columns: COLUMNS, records: [], loading: false, emptyMessage: "nothing here" } }).text()).toContain("nothing here");
    });

    it("renders one row per record on both layouts", () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty" } });

        expect(wrapper.findAll("tbody tr")).toHaveLength(2);
        expect(wrapper.findAll("ul li")).toHaveLength(2);
    });

    it("emits the row actions", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty" } });
        const actions = wrapper.findAll("tbody tr")[0].findAll("td:last-child button");

        await actions[0].trigger("click");
        await actions[1].trigger("click");
        await actions[2].trigger("click");

        expect(wrapper.emitted("view")[0]).toEqual([RECORDS[0]]);
        expect(wrapper.emitted("edit")[0]).toEqual([RECORDS[0]]);
        expect(wrapper.emitted("remove")[0]).toEqual([RECORDS[0]]);
    });

    it("hides the write actions when they are closed", () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", canEdit: false, canDelete: false } });

        expect(wrapper.findAll("tbody tr")[0].findAll("td:last-child button")).toHaveLength(1);
    });

    it("takes a clicked row to the edit screen when it may be edited", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty" } });

        await wrapper.findAll("tbody tr")[1].trigger("click");

        expect(wrapper.emitted("edit")[0]).toEqual([RECORDS[1]]);
        expect(wrapper.emitted("view")).toBeUndefined();
        expect(wrapper.findAll("tbody tr")[1].classes()).toContain("cursor-pointer");
    });

    it("takes a clicked row to the read screen when editing is closed", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", canEdit: false } });

        await wrapper.findAll("tbody tr")[1].trigger("click");

        expect(wrapper.emitted("view")[0]).toEqual([RECORDS[1]]);
        expect(wrapper.emitted("edit")).toBeUndefined();
    });

    it("leaves a row inert when it leads nowhere", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", canView: false, canEdit: false } });

        await wrapper.findAll("tbody tr")[1].trigger("click");

        expect(wrapper.emitted("view")).toBeUndefined();
        expect(wrapper.emitted("edit")).toBeUndefined();
        expect(wrapper.findAll("tbody tr")[1].classes()).not.toContain("cursor-pointer");
    });

    it("hides the read action when reading is closed", () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", canView: false } });

        expect(wrapper.findAll("tbody tr")[0].findAll("td:last-child button")).toHaveLength(2);
    });

    it("cycles the sort of a column", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", ordering: "code", orderable: ["code", "name"] } });

        await wrapper.find("thead button").trigger("click");

        expect(wrapper.emitted("sort")[0]).toEqual(["-code"]);

        await wrapper.setProps({ ordering: "-code" });
        await wrapper.find("thead button").trigger("click");

        expect(wrapper.emitted("sort")[1]).toEqual(["code"]);
    });

    it("points the arrow the way the column is ordered", async () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", ordering: "code", orderable: ["code", "name"] } });
        const header = wrapper.findAll("thead th")[0];

        expect(header.find("svg").exists()).toBe(true);
        expect(header.find("svg").classes(), "ascending points up").toContain("rotate-180");

        await wrapper.setProps({ ordering: "-code" });

        expect(header.find("svg").classes(), "descending points down").not.toContain("rotate-180");
    });

    it("marks no arrow on the columns it is not ordered by", () => {
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", ordering: "-code", orderable: ["code", "name"] } });
        const headers = wrapper.findAll("thead th");

        expect(headers[0].find("svg").exists()).toBe(true);
        expect(headers[1].find("svg").exists()).toBe(false);
    });
});

describe("DataGrid sorting", () => {
    it("offers no sort on a column the api cannot order by", () => {
        // A header that sorted by nothing would answer the same list and read as an order that exists.
        const wrapper = mount(DataGrid, { props: { columns: COLUMNS, records: RECORDS, emptyMessage: "empty", orderable: ["code"] } });
        const headers = wrapper.findAll("thead th");

        expect(headers[0].find("button").exists()).toBe(true);
        expect(headers[1].find("button").exists()).toBe(false);
        expect(headers[1].text()).not.toBe("");
    });
});

describe("the icons of the panel", () => {
    const namesIn = (source, pattern) => [...source.matchAll(pattern)].flatMap((found) => found.slice(1)).filter(Boolean);

    const asked = () => {
        const names = new Set();

        const walk = (folder) => {
            readdirSync(folder, { withFileTypes: true }).forEach((entry) => {
                const full = `${folder}/${entry.name}`;

                if (entry.isDirectory()) {
                    return walk(full);
                }

                if (!/\.(vue|js)$/.test(entry.name)) {
                    return;
                }

                const source = readFileSync(full, "utf8");

                namesIn(source, /<AppIcon[^>]*?\bname="([\w-]+)"/gs).forEach((name) => names.add(name));
                namesIn(source, /\bicon="([\w-]+)"/g).forEach((name) => names.add(name));
                namesIn(source, /\bicon:\s*"([\w-]+)"/g).forEach((name) => names.add(name));
                // What sits on the other side of a comparison is a value being tested, and never the name of a glyph.
                namesIn(source, /:(?:name|icon)="([^"]*)"/g).forEach((expression) => namesIn(expression.replace(/[!=]==?\s*'[\w-]+'/g, ""), /'([\w-]+)'/g).forEach((name) => names.add(name)));
                namesIn(source, /icon:\s*\{[^}]*default:\s*["']([\w-]+)["']/gs).forEach((name) => names.add(name));
            });
        };

        walk("src");

        return names;
    };

    const declared = () => {
        const table = readFileSync("src/components/ui/AppIcon.vue", "utf8").match(/const PATHS = \{([\s\S]*?)\n\};/);

        return [...table[1].matchAll(/^ {4}"?([\w-]+)"?:/gm)].map((found) => found[1]);
    };

    // A glyph nobody draws is dead weight in every bundle, and one nobody declared drew the info glyph in its place.
    it("declares what the screens ask for, and nothing besides", () => {
        const drawn = declared();
        const wanted = asked();

        expect(drawn.length).toBeGreaterThanOrEqual(30);
        expect(drawn.filter((name) => !wanted.has(name))).toEqual([]);
        expect([...wanted].filter((name) => name !== "icon" && !drawn.includes(name))).toEqual([]);
    });

    it("is never reached by falling through, so a name nobody declared is seen", () => {
        expect(readFileSync("src/components/ui/AppIcon.vue", "utf8")).not.toMatch(/\|\|\s*PATHS\./);
    });
});

describe("the tone of the panel", () => {
    const tonesOf = (name) => {
        const table = readFileSync(`src/components/ui/${name}.vue`, "utf8").match(/const TONES = \{([\s\S]*?)\n\};/);

        return [...table[1].matchAll(/^ {4}(\w+):/gm)].map((found) => found[1]);
    };

    it("is one vocabulary, so the same red is not called two things", () => {
        const alert = tonesOf("AppAlert");
        const badge = tonesOf("AppBadge");

        expect(alert.length).toBeGreaterThan(3);
        expect(badge.length).toBeGreaterThan(3);

        // A badge draws tones an alert has no use for, but a tone both know is named the same in both.
        expect(alert.filter((tone) => !badge.includes(tone))).toEqual([]);
    });

    it("is never reached by falling through, because a tone nobody declared has to be seen", () => {
        // Naming the components is naming the ones somebody remembered, and the toast was the one left out.
        const written = readdirSync("src/components/ui").map((name) => [name, readFileSync(`src/components/ui/${name}`, "utf8")]);
        const declaring = written.filter(([, source]) => /^const (TONES|VARIANTS|SIZES) = \{/m.test(source));
        const falling = declaring.filter(([, source]) => /\|\|\s*(TONES|VARIANTS|SIZES)\./.test(source)).map(([name]) => name);

        expect(declaring.length).toBeGreaterThanOrEqual(4);
        expect(falling).toEqual([]);
    });

    it("draws a tone for every way the store raises one", () => {
        const toast = readFileSync("src/components/ui/ToastStack.vue", "utf8");
        const store = readFileSync("src/stores/ui.js", "utf8");
        const raised = [...store.matchAll(/(\w+): \(message\) => notify\("(\w+)"/g)].map((found) => found[2]);
        const drawn = tonesOf("ToastStack");

        expect(raised.length).toBe(3);
        expect(toast).not.toContain("notify,");
        expect(raised.filter((tone) => !drawn.includes(tone))).toEqual([]);
    });
});

describe("every button of the panel", () => {
    // An icon is drawn aria-hidden, so a button holding nothing else is announced as an empty one.
    it("that draws only an icon says what it does", () => {
        const walk = (folder) =>
            readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
                const full = `${folder}/${entry.name}`;

                return entry.isDirectory() ? walk(full) : entry.name.endsWith(".vue") ? [full] : [];
            });

        const unnamed = [];
        let read = 0;

        for (const path of walk("src")) {
            for (const found of readFileSync(path, "utf8").matchAll(/<button\b(?![^>]*:?aria-label)(?![^>]*:?title)[^>]*>([\s\S]*?)<\/button>/g)) {
                read += 1;

                const inner = found[1].replace(/<AppIcon[^>]*\/?>|<svg[\s\S]*?<\/svg>/g, "").trim();

                if (!inner) {
                    unnamed.push(`${path.split("/").pop()}: ${found[0].slice(0, 50)}`);
                }
            }
        }

        expect(read).toBeGreaterThan(5);
        expect(unnamed).toEqual([]);
    });
});
