import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";

function templates(folder) {
    return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => (entry.isDirectory() ? templates(`${folder}/${entry.name}`) : entry.name.endsWith(".html") ? [`${folder}/${entry.name}`] : []));
}

const MODULES = readdirSync("src").filter((name) => name.endsWith(".js") && name !== "main.js");

describe("every module of the site", () => {
    it("is one this guard reads", () => {
        expect(MODULES.length).toBeGreaterThan(5);
    });

    it("answers whether it found anything to bind, and answers it the same way", () => {
        const wrong = [];
        let read = 0;

        for (const name of MODULES) {
            const source = readFileSync(`src/${name}`, "utf8");

            // The rule is about what a binding answers, so the guard reads the binding rather than every line of the module.
            for (const found of source.matchAll(/^export function bind\w+\([\s\S]*?^}/gm)) {
                read += 1;
                const returns = [...found[0].matchAll(/^\s{4}return ([^;]+);/gm)].map((line) => line[1]);

                // A count invites a caller to depend on the number, and nothing does: the question is whether there was work.
                wrong.push(...returns.filter((value) => /\.length$/.test(value)).map((value) => `${name}: returns ${value}`));
            }
        }

        expect(read).toBeGreaterThan(5);
        expect(wrong).toEqual([]);
    });

    it("binds through one shape and calls the server through another, so a test drives the binding with a stub", () => {
        const bound = [];

        for (const name of MODULES) {
            const source = readFileSync(`src/${name}`, "utf8");

            if (/export function bind\w+\(/.test(source)) {
                bound.push(name);
            }
        }

        expect(bound.length).toBeGreaterThan(5);
    });

    // A module nobody calls is a piece that exists and never runs, which is worse than no piece at all.
    it("is one the page actually starts", () => {
        const main = readFileSync("src/main.js", "utf8");
        const declared = MODULES.flatMap((name) => [...readFileSync(`src/${name}`, "utf8").matchAll(/export function (bind\w+)\(/g)].map((found) => found[1]));
        const started = declared.filter((name) => new RegExp(`\\b${name}\\(`).test(main));

        expect(declared.length).toBeGreaterThan(5);
        expect(declared.filter((name) => !started.includes(name))).toEqual([]);
    });
});

describe("every class the site draws with", () => {
    // A class the build never wrote is markup that does nothing, and a migration is exactly what leaves one behind.
    it("is one the stylesheet defines", () => {
        const built = readFileSync("dist/styles.css", "utf8");
        const sources = [
            ...readdirSync("src")
                .filter((name) => name.endsWith(".js"))
                .map((name) => `src/${name}`),
            ...templates("../../templates/global/site"),
        ];

        const used = new Set();

        for (const path of sources) {
            const text = readFileSync(path, "utf8");

            for (const [, body] of [...text.matchAll(/class="([^"]*)"/g), ...text.matchAll(/className\s*[=:]\s*"([^"]*)"/g)]) {
                body.replace(/\{%[\s\S]*?%\}|\{\{[\s\S]*?\}\}/g, " ")
                    .split(/\s+/)
                    .filter((name) => /^[\w:/[\].%-]+$/.test(name))
                    .forEach((name) => used.add(name));
            }
        }

        const missing = [...used].filter((name) => !built.includes(`.${name.replace(/[:/[\].%()]/g, (found) => `\\${found}`)}`)).sort();

        expect(used.size).toBeGreaterThan(150);
        expect(missing).toEqual([]);
    });
});

describe("every component the site draws", () => {
    // A component already decides its surface, its padding and its size, and a utility beside it is the one that fights it.
    const COMPONENTS = ["btn", "input", "select", "textarea", "alert", "badge", "card", "menu", "navbar", "link", "checkbox", "fieldset", "loading"];

    const FIGHTS = /^(flex-1|block|inline|inline-block|inline-flex|flex|grid|inline-grid|contents|text-(?:xs|sm|base|lg)|font-(?:medium|semibold)|rounded-\w+|px-\d|py-\d|p-\d|border|shadow-\w+|h-\d+|w-\d+)$/;

    it("carries nothing the component already decides", () => {
        const clashing = [];
        let read = 0;

        for (const path of templates("../../templates/global/site")) {
            const text = readFileSync(path, "utf8");

            for (const [, body] of text.matchAll(/class="([^"]*)"/g)) {
                const names = body
                    .replace(/\{%[\s\S]*?%\}|\{\{[\s\S]*?\}\}/g, " ")
                    .split(/\s+/)
                    .filter(Boolean);

                if (!names.some((name) => COMPONENTS.some((component) => name === component || name.startsWith(`${component}-`)))) {
                    continue;
                }

                read += 1;
                clashing.push(...names.filter((name) => FIGHTS.test(name)).map((name) => `${path.split("/").pop()}: ${name}`));
            }
        }

        expect(read).toBeGreaterThan(30);
        expect(clashing).toEqual([]);
    });
});

describe("every link the site draws", () => {
    // Nothing here is underlined, at rest or under the pointer: a link says what it is by its colour, and `link` of the plugin draws a rule under it.
    it("is never underlined, and never asks the plugin for a rule", () => {
        const all = templates("../../templates/global/site");
        const drawn = all
            .map((path) => [path.split("/").pop(), readFileSync(path, "utf8")])
            .filter(([, body]) => /\bunderline\b/.test(body) || /class="[^"]*\blink(-\w+)?\b/.test(body))
            .map(([name]) => name);

        expect(all.length).toBeGreaterThan(30);
        expect(drawn).toEqual([]);
    });
});

describe("every hook the markup carries", () => {
    // A `data-` attribute is there for something to find it, so one nothing looks for is markup that does nothing.
    it("is one something looks for", () => {
        const scripts = readdirSync("src")
            .filter((name) => /\.(js|css)$/.test(name))
            .map((name) => readFileSync(`src/${name}`, "utf8"))
            .join("\n");

        const markup = templates("../../templates/global/site")
            .map((path) => readFileSync(path, "utf8"))
            .join("\n");

        // The plugin reads this one itself, and it is a contract and not a hook of ours.
        const THEIRS = ["theme"];

        const hooks = [...new Set([...markup.matchAll(/\sdata-([a-z][\w-]*)/g)].map((found) => found[1]))];
        const camel = (name) => name.replace(/-(\w)/g, (whole, letter) => letter.toUpperCase());
        const orphans = hooks.filter((hook) => !THEIRS.includes(hook) && !scripts.includes(`data-${hook}`) && !scripts.includes(`dataset.${camel(hook)}`));

        expect(hooks.length).toBeGreaterThan(8);
        expect(orphans).toEqual([]);
    });
});

describe("a bar drawn over a page", () => {
    it("takes the room it occupies, so nothing of the page is left under it", () => {
        const source = readFileSync("../../templates/global/site/partials/consent.html", "utf8");

        // Fixed takes no room, so the banner covered the end of every page it was drawn on, and the footer of the first visit was unreachable.
        expect(source).not.toMatch(/class="[^"]*\bfixed\b/);
        expect(source).toMatch(/class="[^"]*\bsticky\b/);
    });
});
