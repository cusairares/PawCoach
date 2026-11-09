import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true -> the app can be opened from a phone on the same Wi-Fi (http://<laptop-ip>:5173)
// proxy      -> /api goes to the backend (python -m server, port 8000), also from the phone
const API_TARGET = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true } },
  },
});
