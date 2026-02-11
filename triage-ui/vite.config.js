/**
 * Vite Configuration
 * ==================
 *
 * Dev server runs on port 3000, proxying API requests
 * to the FastAPI backend on port 8009.
 *
 * Proxy prevents CORS issues during development while
 * keeping the React app on a separate port.
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000,
    open: true,

    // Proxy API calls to the FastAPI triage backend
    proxy: {
      '/api': {
        target: 'http://localhost:8009',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8009',
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
