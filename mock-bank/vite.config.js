import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Fixed port so the agent target URL (http://localhost:5173) is stable and the
// guardrail allowlist can pin it. `host: true` exposes it for a deployed demo.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true, strictPort: true },
  preview: { port: 5173, host: true, strictPort: true },
});
