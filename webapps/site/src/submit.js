// A form sent twice is a second message, a second account or a second purchase, so the second send never leaves.
export function bindSubmits(root) {
    const forms = [...root.querySelectorAll("form")];

    if (!forms.length) {
        return false;
    }

    for (const form of forms) {
        let sent = false;

        form.addEventListener("submit", (event) => {
            if (sent) {
                event.preventDefault();

                // The captcha listens on this same form and would mint a token and send it again on its own.
                event.stopImmediatePropagation();

                return;
            }

            sent = true;

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

    return true;
}
