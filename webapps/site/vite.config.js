import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

import { brandPlugin, declaredPath } from "../declared.js";

export const API_PATH = declaredPath("api_path");

export default defineConfig({
    define: { __API_PATH__: JSON.stringify(API_PATH) },
    plugins: [brandPlugin(fileURLToPath(new URL("./src/brand.css", import.meta.url))), tailwindcss()],
    resolve: {
        alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    // The reCAPTCHA loader is one file both front-ends read from the folder above them.
    server: { fs: { allow: [".."] } },
    build: {
        outDir: "dist",
        emptyOutDir: true,
        // The names are fixed and the version is what busts a cache, so no page has to read a manifest to find a file.
        rollupOptions: {
            input: fileURLToPath(new URL("./src/main.js", import.meta.url)),
            output: { entryFileNames: "scripts.js", assetFileNames: "styles.[ext]" },
        },
    },
});
