import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5181,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8088',
      // Yjs collab rooms (server/app/realtime.py) — must proxy websockets.
      '/ws': { target: 'ws://localhost:8088', ws: true }
    }
  },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node'
  }
});
