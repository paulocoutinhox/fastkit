// A number is written the way its country writes it, and a zero of the mask is a digit somebody types.
export function written(mask, typed) {
    const digits = typed.replace(/\D/g, "");
    let written = "";
    let taken = 0;

    for (const character of mask) {
        if (taken >= digits.length) {
            break;
        }

        if (character === "0") {
            written += digits[taken];
            taken += 1;

            continue;
        }

        written += character;
    }

    return written;
}

// Rewriting the value moves the caret to the end, so the place it goes back to is counted in digits rather than in characters.
export function caretAfter(written, digits) {
    let seen = 0;

    for (let at = 0; at < written.length; at += 1) {
        if (/\d/.test(written[at])) {
            seen += 1;
        }

        if (seen === digits) {
            return at + 1;
        }
    }

    return written.length;
}

export function bindMasks(root) {
    const inputs = Array.from(root.querySelectorAll("[data-mask]"));

    inputs.forEach((input) => {
        const mask = input.dataset.mask;

        input.value = written(mask, input.value);

        input.addEventListener("input", () => {
            const before = input.value.slice(0, input.selectionStart).replace(/\D/g, "").length;

            input.value = written(mask, input.value);

            if (before > 0) {
                input.setSelectionRange(caretAfter(input.value, before), caretAfter(input.value, before));
            }
        });
    });

    return inputs.length > 0;
}
