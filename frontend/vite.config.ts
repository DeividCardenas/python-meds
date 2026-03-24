import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) {
              return 'vendor-charts'
            }
            if (id.includes('framer-motion') || id.includes('motion-dom') || id.includes('motion-utils')) {
              return 'vendor-motion'
            }
            if (id.includes('@apollo/client') || id.includes('graphql') || id.includes('apollo-upload-client')) {
              return 'vendor-apollo'
            }
            if (id.includes('/react/') || id.includes('/react-dom/')) {
              return 'vendor-react'
            }
          }
          return undefined
        },
      },
    },
  },
})
