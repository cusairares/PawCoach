import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true -> the app can be opened from a phone on the same Wi-Fi (http://<laptop-ip>:5173)
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
});
