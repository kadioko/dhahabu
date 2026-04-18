import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Local dev proxy — not used in Vercel/production builds
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/lightweight-charts')) {
            return 'charting'
          }

          if (id.includes('node_modules/recharts')) {
            return 'analytics'
          }

          if (id.includes('node_modules/@tanstack/react-query') || id.includes('node_modules/axios')) {
            return 'data'
          }

          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/react-router-dom/')
          ) {
            return 'react-core'
          }

          if (id.includes('node_modules/lucide-react') || id.includes('node_modules/date-fns') || id.includes('node_modules/clsx')) {
            return 'ui-kit'
          }
        },
      },
    },
  },
})
