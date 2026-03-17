import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Allow longer timeouts for semantic search / embedding operations
        timeout: 30000,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.warn('[proxy] Backend connection error:', err.message)
          })
        },
      },
    },
  },
  build: {
    // Ensure relative paths for assets so the build works behind any base path
    assetsDir: 'assets',
    sourcemap: false,
  },
})
