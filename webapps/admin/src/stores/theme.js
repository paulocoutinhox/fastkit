import { defineStore } from "pinia";
import { ref, watch } from "vue";

export const THEME_STORAGE_KEY = "fastkit_admin_theme";

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

    // The class follows the choice in the same tick, so no frame is drawn in the palette that was just left.
    watch(chosen, draw, { immediate: true, flush: "sync" });

    function choose(theme) {
        chosen.value = THEMES.includes(theme) ? theme : "system";
        localStorage.setItem(THEME_STORAGE_KEY, chosen.value);
    }

    return { chosen, next: () => NEXT[chosen.value], turn: () => choose(NEXT[chosen.value]), choose };
});
