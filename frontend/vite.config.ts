import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import pkg from './package.json';

// 开发代理目标可配置：本机 8000 端口可能被其它应用占用，
// 用 DND_API_TARGET 指向实际后端（例如 http://127.0.0.1:8010）。
const apiTarget = process.env.DND_API_TARGET || 'http://127.0.0.1:8000';
// 开发端口同样可配置：5173 可能被其它本地应用占用
const devPort = Number(process.env.DND_DEV_PORT || 5173);
const proxy = {
  '/api': { target: apiTarget, changeOrigin: true },
  '/media': { target: apiTarget, changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  // 版本号以 package.json 为唯一来源，避免界面上的版本标签再次写死后过期
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
    port: devPort,
    strictPort: true,
    proxy,
  },
  // 预览已构建产物（npm run build 之后），同样代理后端接口；
  // 部分环境下 vite dev server 会卡在依赖优化，preview 更稳定。
  preview: {
    port: devPort,
    strictPort: true,
    proxy,
  },
});
