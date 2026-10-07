import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const API_TARGET = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": API_TARGET,
      "/health": API_TARGET,
    },
  },
  test: {
    environment: "node",
    include: ["../../tests/web/**/*.test.ts"],
  },
});
