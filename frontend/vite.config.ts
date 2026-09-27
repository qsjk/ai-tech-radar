// Vite build of the SPA served by Caddy (VII §37.3, ADR-0013): hashed assets under /assets, no inline script.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    // Never inline assets as data: URIs in scripts; CSS Modules are extracted to hashed files (E20).
    assetsInlineLimit: 0,
  },
});
