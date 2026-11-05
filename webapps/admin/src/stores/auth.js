import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api, configure } from "@/api/client";
import { usePermissionsStore } from "@/stores/permissions";

export const TOKEN_STORAGE_KEY = "admin.token";

export const useAuthStore = defineStore("auth", () => {
    const token = ref(localStorage.getItem(TOKEN_STORAGE_KEY));
    // The account is read from the api on every boot before a screen is drawn, so it lives in memory and never in storage.
    const user = ref(null);
    const sessionRevision = ref(0);

    const isSignedIn = computed(() => Boolean(token.value));
    // Whoever reads with no account reads in UTC, which is the rule of the site too.
    const timezone = computed(() => user.value?.timezone ?? "UTC");

    configure({ token: token.value });

    function apply(nextToken, nextUser) {
        // What the account before this one reached is not what this one reaches.
        usePermissionsStore().forget();

        sessionRevision.value += 1;
        token.value = nextToken;
        user.value = nextUser;

        configure({ token: nextToken });

        if (nextToken) {
            localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);

            return;
        }

        localStorage.removeItem(TOKEN_STORAGE_KEY);
    }

    async function authenticate(path, values) {
        const requestedRevision = sessionRevision.value;
        const payload = await api.post(path, values);

        if (requestedRevision !== sessionRevision.value) {
            return null;
        }

        apply(payload.token, payload.user);

        return payload.user;
    }

    function signIn(login, password, captchaAnswer, captchaToken) {
        return authenticate("/admin/signin", { login, password, captchaAnswer, captchaToken });
    }

    function signInWithCode(challenge, code) {
        return authenticate("/auth/email/confirm", { challenge, code, surface: "admin" });
    }

    function redeemTicket(ticket) {
        return authenticate("/admin/social/redeem", { ticket });
    }

    function remember(account, requestedRevision) {
        if (requestedRevision !== sessionRevision.value) {
            return null;
        }

        user.value = account;

        return account;
    }

    async function refresh() {
        const requestedRevision = sessionRevision.value;
        const account = await api.get("/account/me");

        return remember(account, requestedRevision);
    }

    // A new password ends every session the old one opened, and this device stays in with the token the route answered.
    // It is not the same as another account arriving, so what this one reaches is left alone and the menu does not empty itself.
    function settle(nextToken, account, requestedRevision) {
        const remembered = remember(account, requestedRevision);

        if (remembered === null) {
            return null;
        }

        sessionRevision.value += 1;
        token.value = nextToken;

        localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
        configure({ token: nextToken });

        return remembered;
    }

    function signOut() {
        apply(null, null);
    }

    return { token, user, sessionRevision, isSignedIn, timezone, signIn, signInWithCode, redeemTicket, signOut, apply, refresh, remember, settle };
});
