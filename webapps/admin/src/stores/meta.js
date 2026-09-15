import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";

export const useMetaStore = defineStore("meta", () => {
    const name = ref("");
    const environment = ref("");
    const version = ref("");
    const storageBaseUrl = ref("");
    const enums = ref({});
    const providerCredentials = ref({});
    const timezones = ref([]);
    const languages = ref([]);
    const loaded = ref(false);

    async function load() {
        if (loaded.value) {
            return;
        }

        const [payload, offered] = await Promise.all([api.get("/meta"), api.get("/languages/active")]);

        name.value = payload.name;
        environment.value = payload.environment;

        // The tab of the panel carries the name the api answers, so nothing on this side declares it a second time.
        document.title = payload.name;
        version.value = payload.version;
        storageBaseUrl.value = payload.storageBaseUrl;
        enums.value = payload.enums;
        providerCredentials.value = payload.providerCredentials;
        timezones.value = payload.timezones;
        languages.value = offered;
        loaded.value = true;
    }

    function options(name) {
        return enums.value[name] || [];
    }

    // A gateway names its own secrets, so the form asks for what its panel actually shows.
    function credentialsOf(provider) {
        return providerCredentials.value[provider] || [];
    }

    return { name, environment, version, storageBaseUrl, enums, providerCredentials, timezones, languages, loaded, load, options, credentialsOf };
});
