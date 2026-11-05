// The header collapses on a narrow screen, and the button is the only way back to the links.
export function bindMenu(root) {
    const toggle = root.querySelector("[data-menu-toggle]");
    const menu = root.querySelector("[data-menu]");

    if (!toggle || !menu) {
        return false;
    }

    toggle.setAttribute("aria-expanded", "false");

    toggle.addEventListener("click", () => {
        const opened = menu.classList.toggle("flex");

        menu.classList.toggle("hidden", !opened);
        toggle.setAttribute("aria-expanded", String(opened));
    });

    return true;
}
