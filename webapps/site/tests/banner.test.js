import { beforeEach, describe, expect, it, vi } from "vitest";

import { bindBanners, sendCount } from "@/banner";

function build() {
    document.body.dataset.tenant = "acme";
    document.body.innerHTML = '<a data-banner="uuid-1" href="/one"></a><a data-banner="uuid-2" href="/two"></a>';

    return document.body;
}

describe("the banner counter", () => {
    beforeEach(() => {
        vi.stubGlobal("IntersectionObserver", undefined);
    });

    it("counts a click on the banner that was clicked", () => {
        const root = build();
        const send = vi.fn();

        expect(bindBanners(root, send)).toBe(true);

        root.querySelector('[data-banner="uuid-2"]').dispatchEvent(new Event("click"));

        expect(send).toHaveBeenCalledWith("uuid-2", "click");
    });

    it("counts a view only once the banner reached the screen", () => {
        const observed = [];
        let notify;

        vi.stubGlobal(
            "IntersectionObserver",
            class {
                constructor(callback) {
                    notify = callback;
                }
                observe(element) {
                    observed.push(element);
                }
                unobserve(element) {
                    observed.splice(observed.indexOf(element), 1);
                }
            },
        );

        const root = build();
        const send = vi.fn();

        bindBanners(root, send);

        // A banner further down the page was seen by nobody, so nothing is counted until it arrives.
        expect(send).not.toHaveBeenCalled();

        notify([
            { isIntersecting: true, target: observed[0] },
            { isIntersecting: false, target: observed[1] },
        ]);

        expect(send).toHaveBeenCalledTimes(1);
        expect(send).toHaveBeenCalledWith("uuid-1", "view");
    });

    it("counts a banner that arrived once and never again", () => {
        const observed = [];
        let notify;

        vi.stubGlobal(
            "IntersectionObserver",
            class {
                constructor(callback) {
                    notify = callback;
                }
                observe(element) {
                    observed.push(element);
                }
                unobserve(element) {
                    observed.splice(observed.indexOf(element), 1);
                }
            },
        );

        const root = build();
        const send = vi.fn();

        bindBanners(root, send);

        const banner = observed[0];

        notify([{ isIntersecting: true, target: banner }]);
        notify([{ isIntersecting: true, target: banner }]);

        // Scrolling past it twice is one view, and the server settles the rest by visitor and by day.
        expect(send).toHaveBeenCalledTimes(1);
    });

    it("binds nothing on a page carrying no banner", () => {
        document.body.innerHTML = "<main></main>";

        expect(bindBanners(document.body, vi.fn())).toBe(false);
    });

    it("names the tenant the page belongs to, because the api resolves a brand by that header", () => {
        build();

        const fetcher = vi.fn();
        vi.stubGlobal("fetch", fetcher);

        sendCount("uuid-1", "view");

        const [address, options] = fetcher.mock.calls[0];

        expect(address).toBe(`${__API_PATH__}/banners/uuid-1/view`);
        expect(options.headers["x-tenant-code"]).toBe("acme");
        expect(options.keepalive).toBe(true);
    });

    it("names no tenant where this instance serves a single site", () => {
        build();
        delete document.body.dataset.tenant;

        const fetcher = vi.fn();
        vi.stubGlobal("fetch", fetcher);

        sendCount("uuid-1", "view");

        expect(fetcher.mock.calls[0][1].headers["x-tenant-code"]).toBeUndefined();
    });
});
