import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const blockDotfiles = (): Plugin => ({
  name: 'block-dotfiles',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const urlPath = (req.url || '').split('?')[0]
      if (
        (urlPath.startsWith('/.') && !urlPath.startsWith('/.well-known/')) ||
        urlPath.startsWith('/etc/') ||
        urlPath.startsWith('/proc/') ||
        urlPath.includes('/.')
      ) {
        res.statusCode = 404
        res.end('Not Found')
        return
      }
      next()
    })
  },
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), blockDotfiles()],
  server: {
    host: '0.0.0.0',
    port: 8089,
    allowedHosts: true,
    hmr: {
      overlay: false,
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 8089,
    allowedHosts: true,
  }
})
