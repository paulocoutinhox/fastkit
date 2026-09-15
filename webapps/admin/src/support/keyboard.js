import { nextTick, onBeforeUnmount, watch } from "vue";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

// A panel declared modal keeps the keyboard inside it and hands the focus back when it closes, or tabbing walks through the page it is covering.
export function holdKeyboard(open, panel, close, landing = (reachable) => reachable[0]) {
    let opener = null;

    function reachable() {
        return [...panel.value.querySelectorAll(FOCUSABLE)];
    }

    function onKeydown(event) {
        if (event.key === "Escape") {
            close();
            return;
        }

        if (event.key !== "Tab" || !panel.value) {
            return;
        }

        const found = reachable();
        const first = found[0];
        const last = found[found.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
            return;
        }

        if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    async function enter() {
        opener = document.activeElement;
        await nextTick();

        // Closing in the same tick it opened leaves nothing drawn to focus.
        if (!panel.value) {
            return;
        }

        landing(reachable())?.focus();
    }

    // What opened the panel may be gone, the trash button of the row it just deleted, and then focus lands on the content of the screen.
    function leave() {
        (opener?.isConnected ? opener : document.querySelector("main"))?.focus();
        opener = null;
    }

    watch(open, (value) => {
        document.body.classList.toggle("overflow-hidden", value);

        if (value) {
            window.addEventListener("keydown", onKeydown);
            enter();
            return;
        }

        window.removeEventListener("keydown", onKeydown);
        leave();
    });

    onBeforeUnmount(() => {
        document.body.classList.remove("overflow-hidden");
        window.removeEventListener("keydown", onKeydown);
    });
}
