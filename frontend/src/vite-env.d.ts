/// <reference types="vite/client" />

/** 构建时注入：来源 frontend/package.json 的 version（见 vite.config.ts 的 define）。 */
declare const __APP_VERSION__: string;
