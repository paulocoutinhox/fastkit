// A form sent twice is a second message, a second account or a second purchase, so the second send never leaves.
export function bindSubmits(root) {
    const forms = [...root.querySelectorAll("form")];

    if (!forms.length) {
        return false;
    }

    const sent = new Set();

    for (const form of forms) {
        form.addEventListener("submit", (event) => {
            if (sent.has(form)) {
                event.preventDefault();

                // The captcha listens on this same form and would mint a token and send it again on its own.
                event.stopImmediatePropagation();

                return;
            }

            sent.add(form);

            // The button is marked and never disabled, because a disabled one stops carrying the name and value the server reads.
            const button = event.submitter;

            if (!button) {
                return;
            }

            button.setAttribute("data-busy", "");
            button.setAttribute("aria-busy", "true");
            button.prepend(Object.assign(document.createElement("span"), { className: "loading loading-spinner loading-sm" }));
        });
    }

    // A page brought back by the back button is the page as it was left, sent forms included, and every one of them can be sent again from there.
    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) {
            return;
        }

        sent.clear();

        for (const button of root.querySelectorAll("[data-busy]")) {
            button.removeAttribute("data-busy");
            button.removeAttribute("aria-busy");
            button.querySelector(".loading")?.remove();
        }
    });

    return true;
}
