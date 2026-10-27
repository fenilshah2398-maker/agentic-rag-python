import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Browser calls http://localhost:5173/api/auth/signin
      // Vite forwards it to http://127.0.0.1:8000/auth/signin
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // The chat page opens ws://localhost:5173/ws/chat.
      // Vite keeps that socket open and connects it to FastAPI.
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
})