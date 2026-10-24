import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { localResultPlugin } from "./localResultPlugin";

export default defineConfig({
  plugins: [react(), localResultPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, "")
      }
    }
  }
});
