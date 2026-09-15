// A postal code is a whole address in the countries that have somebody to ask, and the fields already filled in are left alone.
const FILLED = ["line1", "district", "city", "state"];

export function bindPostalCode(root, lookup) {
    const form = root.querySelector("[data-address-form]");

    if (!form) {
        return false;
    }

    const offered = (form.getAttribute("data-postal-code-countries") || "").split(",").filter(Boolean);
    const country = form.querySelector('[name="country_code"]');
    const code = form.querySelector('[name="postal_code"]');
    const status = form.querySelector("[data-postal-code-status]");

    let sequence = 0;

    code.addEventListener("blur", () => {
        if (!offered.includes(country.value) || !code.value.trim()) {
            return;
        }

        // A field is only filled while it is empty, so an older answer arriving first would leave the address of a code the visitor already replaced.
        const attempt = (sequence += 1);

        status.classList.remove("hidden");

        lookup(form.getAttribute("data-postal-code-url"), country.value, code.value)
            .then((place) => {
                if (attempt !== sequence) {
                    return;
                }

                status.classList.add("hidden");

                if (place) {
                    FILLED.forEach((name) => fill(form, name, place[name]));
                }
            })
            .catch(() => {
                if (attempt === sequence) {
                    status.classList.add("hidden");
                }
            });
    });

    return true;
}

function fill(form, name, value) {
    const field = form.querySelector(`[name="${name}"]`);

    // What the visitor already wrote is theirs, so the lookup only ever fills what is still empty.
    if (field && !field.value.trim() && value) {
        field.value = value;
    }
}

export function fetchPostalCode(url, country, code) {
    return fetch(`${url}?country=${encodeURIComponent(country)}&code=${encodeURIComponent(code)}`).then((answer) => (answer.ok ? answer.json() : null));
}
