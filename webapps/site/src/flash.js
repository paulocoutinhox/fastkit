// A notice is read once, and closing it is the reader saying so.
export function bindFlashes(root) {
    const buttons = Array.from(root.querySelectorAll("[data-flash-close]"));

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const notice = button.closest("[data-flash]");

            if (notice) {
                notice.remove();
            }
        });
    });

    return buttons.length > 0;
}
