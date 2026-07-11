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
      '/auth': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/users': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/projects': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/data-sources': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/calculations': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/reports': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/review-queue': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/dashboard': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/webhooks': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/whatsapp': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/orchestrator': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/audit': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/compliance': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/brokerage': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/tokenization': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/corporate': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/leads': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/validation-engine': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/vvb': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/validation': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/fields': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/command-center': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/admin': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/metrics': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8001', ws: true },
    },
  },
})
