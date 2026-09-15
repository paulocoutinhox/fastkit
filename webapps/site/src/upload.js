// A file field draws nothing of its own, so the name of what was chosen is written where the empty label was.
export function bindUploads(root) {
    const inputs = Array.from(root.querySelectorAll("[data-upload-input]"));

    inputs.forEach((input) => {
        const label = input.parentElement.querySelector("[data-upload-name]");
        const empty = label.textContent;

        input.addEventListener("change", () => {
            label.textContent = input.files.length > 0 ? input.files[0].name : empty;
        });
    });

    return inputs.length > 0;
}
