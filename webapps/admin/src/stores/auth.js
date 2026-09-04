import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api, configure } from "@/api/client";
import { usePermissionsStore } from "@/stores/permissions";

export const TOKEN_STORAGE_KEY = "fastkit.token";
export const USER_STORAGE_KEY = "fastkit.user";

function readStoredUser() {
    try {
        return JSON.parse(localStorage.getItem(USER_STORAGE_KEY)) || null;
    } catch {
        return null;
    }
}

export const useAuthStore = defineStore("auth", () => {
    const token = ref(localStorage.getItem(TOKEN_STORAGE_KEY));
    const user = ref(readStoredUser());

    const isSignedIn = computed(() => Boolean(token.value));
    const timezone = computed(() => user.value?.timezone || null);

    configure({ token: token.value });

    function apply(nextToken, nextUser) {
        // What the account before this one reached is not what this one reaches.
        usePermissionsStore().forget();

        token.value = nextToken;
        user.value = nextUser;

        configure({ token: nextToken });

        if (nextToken) {
            localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
            localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser));

            return;
        }

        localStorage.removeItem(TOKEN_STORAGE_KEY);
        localStorage.removeItem(USER_STORAGE_KEY);
    }

    async function signIn(login, password, captchaAnswer, captchaToken) {
        const payload = await api.post("/admin/signin", { login, password, captchaAnswer, captchaToken });

        apply(payload.token, payload.user);
    }

    function signOut() {
        apply(null, null);
    }

    return { token, user, isSignedIn, timezone, signIn, signOut, apply };
});
