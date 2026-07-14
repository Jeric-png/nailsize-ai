import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // The runtime files are pinned in public/ort and audited separately. This
    // avoids Vite emitting a second 13 MB WASM copy with a generated name.
    conditions: ["onnxruntime-web-use-extern-wasm"],
  },
  server: { port: 5173 },
  build: { manifest: "asset-manifest.json", sourcemap: false },
});
