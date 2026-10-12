import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Set VITE_API=real to talk to the actual service; the dev server proxies /v1 to it.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/v1": process.env.VITE_API_TARGET ?? "http://localhost:8080" } },
  test: { environment: "node" },
});
