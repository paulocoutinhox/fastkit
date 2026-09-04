// What a control says when the form refused it, because the colour it turns is the half a reader who cannot see the screen never gets.
export function names(inputId, error) {
    return error ? { "aria-describedby": `${inputId}-error` } : {};
}

// A role with no valid state has nothing to announce as invalid, which a button opening a popup is, so that one only names the message.
export function refused(inputId, error) {
    return error ? { "aria-invalid": "true", ...names(inputId, error) } : {};
}
