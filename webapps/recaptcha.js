const SCRIPT_URL = "https://www.google.com/recaptcha/api.js?render=";

let loading = null;

// The script is asked for once per page, and whoever arrives while it is still loading waits on that same load instead of reading a global that is not there yet.
function loaded(siteKey, document) {
    loading ??= new Promise((resolve, reject) => {
        const script = document.createElement("script");

        script.src = `${SCRIPT_URL}${siteKey}`;
        script.async = true;
        script.onload = () => resolve(window.grecaptcha);
        script.onerror = () => reject(new Error("recaptcha did not load"));

        document.head.appendChild(script);
    }).catch((error) => {
        // A load that failed is forgotten, so the next form sent asks for the script again instead of failing with the same answer for good.
        loading = null;

        throw error;
    });

    return loading;
}

// The v3 challenge asks nothing of the person, so the site and the panel both mint the token right before a form is sent.
// A challenge Google refuses to mint has to fail, because a promise that never settles is a form that never leaves.
export async function mintRecaptcha(siteKey, action, document) {
    const grecaptcha = await loaded(siteKey, document);

    return new Promise((resolve, reject) => grecaptcha.ready(() => grecaptcha.execute(siteKey, { action }).then(resolve, reject)));
}
