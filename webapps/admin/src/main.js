import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { configure } from "./api/client";
import { i18n } from "./i18n";
import { createAppRouter } from "./router";
import { useAuthStore } from "./stores/auth";

import "./style.css";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(i18n);

configure({ locale: i18n.global.locale.value });

const router = createAppRouter();

configure({
    onUnauthorized: () => {
        // Only the session ends here: clearing the whole storage would take the chosen language with it.
        useAuthStore().signOut();
        router.push({ name: "login" });
    },
});

app.use(router);
app.mount("#app");
