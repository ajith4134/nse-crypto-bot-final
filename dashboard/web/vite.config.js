import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build to ../static so the existing stdlib Python server (dashboard/server.py)
// serves the compiled React app directly. base './' keeps asset paths relative
// so it works behind the localtunnel subdomain. emptyOutDir:false preserves the
// legacy architecture.html / knowledge.html pages alongside the new index.html.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../static',
    emptyOutDir: false,
    // Unique asset dir (NOT 'assets') so the dashboard's hashed chunks never
    // collide with OpenAlgo's /assets/*. The gateway then routes /assets/* →
    // OpenAlgo :5000 DIRECTLY (no fragile dashboard-first two-hop that blanked
    // OpenAlgo when the bounded dashboard server choked under parallel load).
    assetsDir: 'dash-assets',
    chunkSizeWarningLimit: 2000,
  },
  server: { port: 5173 },
})
