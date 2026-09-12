import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // 首屏体积：把变化频率低的第三方库拆成独立 chunk。
    // React 与 framer-motion 走长期缓存，业务代码改动不再让用户重下 500KB。
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          motion: ['framer-motion'],
          state: ['zustand'],
        },
      },
    },
    // 拆包后单文件阈值收紧，超过说明又有大依赖混进业务 chunk
    chunkSizeWarningLimit: 320,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
