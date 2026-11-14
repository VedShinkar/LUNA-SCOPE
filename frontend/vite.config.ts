import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const proxy = { '/terrain': process.env.LUNA_TERRAIN_API ?? 'http://127.0.0.1:8000' }
export default defineConfig({
  plugins: [react()],
  server: { proxy, strictPort: true },
  preview: { proxy, strictPort: true },
})
