const SCRIPT_URL = "https://www.google.com/recaptcha/api.js?render=";

const ACTION = "admin_signin";

// The v3 challenge of reCAPTCHA asks nothing of the person, so the token is minted right before the form is sent.
export function loadRecaptcha(siteKey, document) {
    const existing = document.querySelector(`script[src^="${SCRIPT_URL}"]`);

    if (existing) {
        return Promise.resolve(window.grecaptcha);
    }

    return new Promise((resolve, reject) => {
        const script = document.createElement("script");

        script.src = `${SCRIPT_URL}${siteKey}`;
        script.async = true;
        script.onload = () => resolve(window.grecaptcha);
        script.onerror = () => reject(new Error("recaptcha did not load"));

        document.head.appendChild(script);
    });
}

export async function mintRecaptcha(siteKey, document) {
    const grecaptcha = await loadRecaptcha(siteKey, document);

    // A challenge Google refuses to mint has to fail, because a promise that never settles is a button that spins for good.
    return new Promise((resolve, reject) => grecaptcha.ready(() => grecaptcha.execute(siteKey, { action: ACTION }).then(resolve, reject)));
}
