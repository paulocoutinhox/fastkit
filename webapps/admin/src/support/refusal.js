import { nextTick } from "vue";

// What a control says when the form refused it, because the colour it turns is the half a reader who cannot see the screen never gets.
export function names(inputId, error) {
    return error ? { "aria-describedby": `${inputId}-error` } : {};
}

// A role with no valid state has nothing to announce as invalid, which a button opening a popup is, so that one only names the message.
export function refused(inputId, error) {
    return error ? { "aria-invalid": "true", ...names(inputId, error) } : {};
}

// A refusal is where the keyboard goes next, because a message below a field far down the form is otherwise never seen nor announced.
export async function pointAt(root) {
    await nextTick();
    root?.querySelector('[aria-describedby$="-error"]')?.focus();
}

// A refusal names the field it is about, and one about a field this screen does not draw would otherwise be pointed at nowhere and read as nothing happening.
export function unpointed(error, fields) {
    const drawn = new Set(fields.map((field) => field.name));

    return Object.keys(error.errors || {}).some((name) => drawn.has(name)) ? "" : error.message;
}
