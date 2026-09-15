import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

import { API_PATH } from "./vite.config";

export default defineConfig({
    define: { __API_PATH__: JSON.stringify(API_PATH) },
    resolve: {
        alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./tests/setup.js"],
        coverage: {
            provider: "v8",
            include: ["src/**/*.js"],
            exclude: ["src/main.js"],
            reporter: ["text", "html"],
        },
    },
});
