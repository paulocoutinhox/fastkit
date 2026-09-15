// A banner is counted where it was actually shown, and the reader is named by a cookie this page cannot read.
const MARGIN = "0px";

export function sendCount(uuid, kind) {
    const tenant = document.body.dataset.tenant;
    const named = tenant ? { "x-tenant-code": tenant } : {};

    // The count leaves with the page, so it is kept alive past the click instead of holding the link back.
    return fetch(`${__API_PATH__}/banners/${uuid}/${kind}`, { method: "POST", keepalive: true, credentials: "same-origin", headers: { "content-type": "application/json", ...named }, body: "{}" });
}

export function bindBanners(root, send) {
    const banners = [...root.querySelectorAll("[data-banner]")];
    const viewed = new WeakSet();

    if (!banners.length) {
        return false;
    }

    banners.forEach((banner) => banner.addEventListener("click", () => send(banner.dataset.banner, "click")));

    // A banner further down the page was never seen by anybody, so what counts a view is it reaching the screen.
    if (typeof IntersectionObserver !== "function") {
        return true;
    }

    const seen = new IntersectionObserver(
        (entries) => {
            entries
                .filter((entry) => entry.isIntersecting && !viewed.has(entry.target))
                .forEach((entry) => {
                    viewed.add(entry.target);
                    seen.unobserve(entry.target);
                    send(entry.target.dataset.banner, "view");
                });
        },
        { rootMargin: MARGIN },
    );

    banners.forEach((banner) => seen.observe(banner));

    return true;
}
