// The v3 challenge of reCAPTCHA asks nothing of the visitor, so the page mints the token right before the form is sent.
export function bindRecaptcha(root, loader) {
    const holder = root.querySelector("[data-recaptcha-site-key]");
    const field = root.querySelector("[data-recaptcha-response]");

    if (!holder || !field) {
        return false;
    }

    const siteKey = holder.getAttribute("data-recaptcha-site-key");
    const form = field.closest("form");

    form.addEventListener("submit", async (event) => {
        if (field.value) {
            return;
        }

        event.preventDefault();

        // A challenge nobody could mint is an empty answer, which the server refuses by drawing the page again with the reason.
        field.value = await loader(siteKey).catch(() => "");

        form.submit();
    });

    return true;
}
