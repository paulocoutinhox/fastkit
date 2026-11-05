import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

export const THEME_STORAGE_KEY = "admin.theme";

const THEMES = ["system", "light", "dark"];

// One button carries the whole choice, so it names where the next press lands.
const NEXT = { system: "light", light: "dark", dark: "system" };

function stored() {
    const written = localStorage.getItem(THEME_STORAGE_KEY);

    return THEMES.includes(written) ? written : "system";
}

export const useThemeStore = defineStore("theme", () => {
    const chosen = ref(stored());

    // Which side of every `light-dark` the document uses, which is the whole of what a palette is here.
    function draw() {
        document.documentElement.style.colorScheme = chosen.value === "system" ? "light dark" : chosen.value;
    }

    // The scheme follows the choice in the same tick, so no frame is drawn in the palette that was just left.
    watch(chosen, draw, { immediate: true, flush: "sync" });

    // The device can turn dark while the panel is open, and a computed never hears it unless the answer is a ref the query writes.
    const system = matchMedia("(prefers-color-scheme: dark)");
    const systemDark = ref(system.matches);

    system.addEventListener("change", (event) => (systemDark.value = event.matches));

    // Which palette is drawn right now, for the frames that hold a document of their own and cannot read the one the panel carries.
    const dark = computed(() => chosen.value === "dark" || (chosen.value === "system" && systemDark.value));

    function turn() {
        chosen.value = NEXT[chosen.value];
        localStorage.setItem(THEME_STORAGE_KEY, chosen.value);
    }

    return { chosen, dark, next: () => NEXT[chosen.value], turn };
});
