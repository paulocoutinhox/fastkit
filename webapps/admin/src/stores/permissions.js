import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api } from "@/api/client";

export const usePermissionsStore = defineStore("permissions", () => {
    const reachable = ref([]);
    const reports = ref([]);
    const confined = ref(false);
    const brands = ref(false);
    const loaded = ref(false);
    let generation = 0;

    async function load() {
        if (loaded.value) {
            return;
        }

        const requestedGeneration = generation;
        const answer = await api.get("/meta/permissions");

        if (generation !== requestedGeneration) {
            return;
        }

        reachable.value = answer.resources;
        reports.value = answer.reports;
        confined.value = answer.confined;
        brands.value = answer.brands;
        loaded.value = true;
    }

    // Signing in as somebody else must not answer with what the one before them reached.
    function forget() {
        generation += 1;

        reachable.value = [];
        reports.value = [];
        confined.value = false;
        brands.value = false;
        loaded.value = false;
    }

    const named = computed(() => new Set(reachable.value));

    function reaches(name) {
        return named.value.has(name);
    }

    function reachesReport(code) {
        return reports.value.includes(code);
    }

    // What names a brand is shown only where the instance serves many.
    function shows(item) {
        return !item.branded || brands.value;
    }

    // And a choice is offered only to whoever can make it, which an operator of one brand cannot for a field the server stamps.
    function offers(item) {
        return shows(item) && (!item.unconfined || !confined.value);
    }

    // An operator of one brand may read the shared rows and never write them, which the API answers with a 404, so the panel never offers it.
    // A row whose brand is its parent's is shared when that parent is, which the resource names in `reachesThrough`.
    // A record its resource declares sealed is refused to every operator, so the panel never offers that either.
    function writes(resource, record) {
        const scope = resource.reachesThrough ? record?.[resource.reachesThrough] : record;

        if (confined.value && scope?.tenantId === null) {
            return false;
        }

        return !Object.entries(resource.sealedWhen ?? {}).some(([field, value]) => record?.[field] === value);
    }

    return { reachable, reports, confined, brands, loaded, load, forget, reaches, reachesReport, shows, offers, writes };
});
