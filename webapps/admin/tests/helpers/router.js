import { createMemoryHistory, createRouter } from "vue-router";

import { routes } from "@/router";

export function createTestRouter(initial = "/") {
    const router = createRouter({ history: createMemoryHistory(), routes: routes.map((route) => ({ ...route, component: { template: "<div />" } })) });

    router.push(initial);

    return router;
}
