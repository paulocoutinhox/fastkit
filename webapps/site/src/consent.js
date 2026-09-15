// The answer is written by the server, and this only takes the banner off the page instead of loading it again.
export function bindConsent(root, send) {
    const banner = root.querySelector("[data-consent]");

    if (!banner) {
        return false;
    }

    const form = banner.querySelector("form");

    form.addEventListener("submit", (event) => {
        const chosen = event.submitter;

        if (!chosen) {
            return;
        }

        event.preventDefault();

        const answer = new FormData(form);
        answer.set(chosen.name, chosen.value);

        send(form.getAttribute("action"), answer)
            .then(() => banner.remove())
            .catch(() => form.submit());
    });

    return true;
}

export function sendConsent(action, answer) {
    return fetch(action, { method: "POST", body: answer, redirect: "manual" });
}
