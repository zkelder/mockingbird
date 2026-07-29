import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Keep the final esbuild source-map transform below its 512 KiB JSON boundary.
        manualChunks(id) {
          if (!id.includes("/src/pages/")) return undefined;
          const page = id.split("/src/pages/")[1]?.replace(/\.tsx$/, "");
          return page ? `page-${page}` : undefined;
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
      },
      "/health": {
        target: "http://127.0.0.1:8000",
      },
    },
  },
});
