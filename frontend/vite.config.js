import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    // 生产构建输出到 backend/static（由 FastAPI 单进程伺服，VM 部署无需 Node）
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    port: 5175,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true
      }
    }
  }
})
