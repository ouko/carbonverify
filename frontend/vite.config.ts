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
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/users': { target: 'http://localhost:8000', changeOrigin: true },
      '/projects': { target: 'http://localhost:8000', changeOrigin: true },
      '/data-sources': { target: 'http://localhost:8000', changeOrigin: true },
      '/calculations': { target: 'http://localhost:8000', changeOrigin: true },
      '/reports': { target: 'http://localhost:8000', changeOrigin: true },
      '/review-queue': { target: 'http://localhost:8000', changeOrigin: true },
      '/dashboard': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/uploads': { target: 'http://localhost:8000', changeOrigin: true },
      '/webhooks': { target: 'http://localhost:8000', changeOrigin: true },
      '/whatsapp': { target: 'http://localhost:8000', changeOrigin: true },
      '/orchestrator': { target: 'http://localhost:8000', changeOrigin: true },
      '/audit': { target: 'http://localhost:8000', changeOrigin: true },
      '/compliance': { target: 'http://localhost:8000', changeOrigin: true },
      '/brokerage': { target: 'http://localhost:8000', changeOrigin: true },
      '/tokenization': { target: 'http://localhost:8000', changeOrigin: true },
      '/corporate': { target: 'http://localhost:8000', changeOrigin: true },
      '/leads': { target: 'http://localhost:8000', changeOrigin: true },
      '/validation-engine': { target: 'http://localhost:8000', changeOrigin: true },
      '/vvb': { target: 'http://localhost:8000', changeOrigin: true },
      '/validation': { target: 'http://localhost:8000', changeOrigin: true },
      '/fields': { target: 'http://localhost:8000', changeOrigin: true },
      '/command-center': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/metrics': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
