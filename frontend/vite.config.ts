import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 允许通过内网穿透域名访问(如 cloudflared 临时公网链接);仅本地开发用
    allowedHosts: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
