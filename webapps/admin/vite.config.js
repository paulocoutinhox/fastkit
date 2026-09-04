import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

import { brandPlugin, declaredPath } from "../declared.js";

export const ADMIN_PATH = declaredPath("admin_path");

export const API_PATH = declaredPath("api_path");

export default defineConfig({
    base: `${ADMIN_PATH}/`,
    define: { __API_PATH__: JSON.stringify(API_PATH) },
    plugins: [brandPlugin(fileURLToPath(new URL("./src/brand.css", import.meta.url))), vue(), tailwindcss()],
    resolve: {
        alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
        port: 5173,
        proxy: { [API_PATH]: "http://localhost:8000", "/media": "http://localhost:8000" },
    },
    build: {
        outDir: "dist",
        emptyOutDir: true,
    },
});
