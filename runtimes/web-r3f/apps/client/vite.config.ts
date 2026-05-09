import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    fs: {
      allow: [
        resolve(__dirname, ".."),
        resolve(__dirname, "../../.."),
        resolve(__dirname, "../../../.."),
      ],
    },
  },
  optimizeDeps: {
    exclude: ["@mkkellogg/gaussian-splats-3d"],
  },
  assetsInclude: ["**/*.glb", "**/*.gltf", "**/*.ply", "**/*.splat", "**/*.ksplat"],
  build: {
    target: "es2022",
    sourcemap: true,
  },
});
