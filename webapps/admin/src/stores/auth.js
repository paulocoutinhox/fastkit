import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api, configure } from "@/api/client";
import { usePermissionsStore } from "@/stores/permissions";

export const TOKEN_STORAGE_KEY = "admin.token";
export const USER_STORAGE_KEY = "admin.user";

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

    function remember(account) {
        user.value = account;
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(account));

        return account;
    }

    async function refresh() {
        // What is stored is a snapshot taken at sign in, so a photo or a name changed since then would never reach the screen.
        return remember(await api.get("/account/me"));
    }

    // A new password ends every session the old one opened, and this device stays in with the token the route answered.
    // It is not the same as another account arriving, so what this one reaches is left alone and the menu does not empty itself.
    function settle(nextToken, account) {
        token.value = nextToken;

        localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
        configure({ token: nextToken });

        return remember(account);
    }

    function signOut() {
        apply(null, null);
    }

    return { token, user, isSignedIn, timezone, signIn, signOut, apply, refresh, remember, settle };
});
