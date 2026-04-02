import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


const rootDir = path.dirname(fileURLToPath(import.meta.url));


export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": rootDir
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: true,
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["components/**/*.tsx", "lib/**/*.ts"]
    }
  }
});
