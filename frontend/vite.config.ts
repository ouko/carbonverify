import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-query': ['@tanstack/react-query', 'axios'],
          'vendor-ui': ['lucide-react', 'clsx', 'tailwind-merge'],
        },
      },
    },
  },
  server: {
    port: 5173,
    host: true,
    hmr: {
      host: 'localhost',
      port: 5173,
      protocol: 'ws',
    },
    proxy: {
      // In local development all API calls are proxied to the FastAPI backend.
      // This keeps the SPA and API on the same origin, avoiding CORS issues and
      // matching the production reverse-proxy setup.
      //
      // Prefixes that overlap with React Router page paths use a trailing slash
      // so that a page load (e.g. /projects/new) still serves index.html while
      // API calls (e.g. /projects/) are forwarded to the backend.
      '/auth': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/users': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/webhooks': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/vvb': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/orchestrator': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/whatsapp': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/validation': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/oauth': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/methodology-generator': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/api-keys': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/metrics': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8001', ws: true },
      // Page-conflicting API prefixes (trailing-slash match)
      '/projects/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/data-sources/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/calculations/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/reports/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/review-queue/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/brokerage/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/tokenization/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/compliance/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/audit/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/admin/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/corporate/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/leads/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/applications': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/dashboard/': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
})
