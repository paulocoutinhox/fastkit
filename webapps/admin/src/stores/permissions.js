import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api } from "@/api/client";

export const usePermissionsStore = defineStore("permissions", () => {
    const reachable = ref([]);
    const confined = ref(false);
    const loaded = ref(false);

    async function load() {
        if (loaded.value) {
            return;
        }

        const answer = await api.get("/meta/permissions");

        reachable.value = answer.resources;
        confined.value = answer.confined;
        loaded.value = true;
    }

    // Signing in as somebody else must not answer with what the one before them reached.
    function forget() {
        reachable.value = [];
        confined.value = false;
        loaded.value = false;
    }

    const named = computed(() => new Set(reachable.value));

    function reaches(name) {
        return named.value.has(name);
    }

    return { reachable, confined, loaded, load, forget, reaches };
});
