import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "jsdom", setupFiles: ["ui/setup.ts"], include: ["ui/*.test.tsx"], testTimeout: 30000 } });
