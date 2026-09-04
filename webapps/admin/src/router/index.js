import { createRouter, createWebHistory } from "vue-router";

import { canCreate, canEdit, canView, findResource } from "@/resources";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { usePermissionsStore } from "@/stores/permissions";
import { useUiStore } from "@/stores/ui";
import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";
import NotFoundView from "@/views/NotFoundView.vue";
import ResourceDetailView from "@/views/ResourceDetailView.vue";
import ResourceFormView from "@/views/ResourceFormView.vue";
import ResourceListView from "@/views/ResourceListView.vue";

export const routes = [
    { path: "/login", name: "login", component: LoginView, meta: { anonymous: true } },
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/:resource", name: "resource-list", component: ResourceListView },
    { path: "/:resource/new", name: "resource-create", component: ResourceFormView },
    { path: "/:resource/:id", name: "resource-detail", component: ResourceDetailView },
    { path: "/:resource/:id/edit", name: "resource-edit", component: ResourceFormView },
    { path: "/:pathMatch(.*)*", name: "not-found", component: NotFoundView },
];

// The build writes where the panel answers, so this side never declares it a second time.
const ADMIN_PATH = import.meta.env.BASE_URL.replace(/\/$/, "");

const PERMISSION_BY_ROUTE = { "resource-create": canCreate, "resource-detail": canView, "resource-edit": canEdit };

const RESOURCE_ROUTES = new Set(["resource-list", "resource-create", "resource-detail", "resource-edit"]);

// The URL is a way in like any other, so what the menu refuses to offer it refuses to open.
function allowed(to) {
    if (!RESOURCE_ROUTES.has(to.name)) {
        return true;
    }

    const resource = findResource(to.params.resource);

    if (!resource) {
        return { name: "not-found", params: { pathMatch: to.path.slice(1).split("/") } };
    }

    if (!usePermissionsStore().reaches(resource.name)) {
        return { name: "dashboard" };
    }

    const permits = PERMISSION_BY_ROUTE[to.name];

    return !permits || permits(resource) ? true : { name: "resource-list", params: { resource: resource.name } };
}

export function createAppRouter(history = createWebHistory(ADMIN_PATH)) {
    const router = createRouter({ history, routes, scrollBehavior: () => ({ top: 0 }) });

    router.beforeEach(async (to) => {
        const auth = useAuthStore();

        if (to.meta.anonymous) {
            return auth.isSignedIn ? { name: "dashboard" } : true;
        }

        if (!auth.isSignedIn) {
            return { name: "login" };
        }

        const meta = useMetaStore();
        const permissions = usePermissionsStore();

        if (!meta.loaded || !permissions.loaded) {
            const ui = useUiStore();
            ui.booting = true;

            try {
                await Promise.all([meta.load(), permissions.load()]);
            } catch (error) {
                // The boot screen stays and says what stopped it, because sending a signed in account to the sign in would bounce it back here and start over.
                ui.bootFailure = error.message;

                return false;
            }

            ui.booting = false;
        }

        return allowed(to);
    });

    return router;
}
