/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // 正文：优先系统 UI 字体，保证中英文混排的字重与字面稳定
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        // 展示标题 / 规则书：衬线，营造纸笔跑团的质感
        display: ['Noto Serif SC', 'Songti SC', 'Georgia', 'Times New Roman', 'serif'],
        medieval: ['Georgia', 'Songti SC', 'Times New Roman', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'Liberation Mono', 'monospace'],
      },
      fontSize: {
        // 只补充刻度名称，不覆盖 Tailwind 默认 xs/sm/base，
        // 避免既有布局因为字号变化而错位。
        // 3xs 定为 11px：这是可读性下限（12px 正文 / 11px 微标签），
        // 不要再往下加更小的刻度。
        '3xs': ['11px', { lineHeight: '1.5' }],
        '2xs': ['12px', { lineHeight: '1.55' }],
      },
      colors: {
        // 品牌主色（沿用 indigo 色相，命名 brand 便于后续换肤）
        brand: {
          50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc',
          400: '#818cf8', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca',
          800: '#3730a3', 900: '#312e81',
        },
        // 中性色：偏暖的墨色，比默认 gray 更贴合羊皮纸底色。
        // 可读性约束：ink-400 在白底 5.2:1、在 ink-100 / 浅色 tint 底上仍 ≥4.5:1，
        // 所以 400 是最浅的正文色；300 只做装饰（分隔点、占位块），不承载信息。
        ink: {
          50: '#faf9f7', 100: '#f4f2ee', 200: '#e7e4dd', 300: '#cdc6b8',
          400: '#726c63', 500: '#5f5a53', 600: '#514c46', 700: '#3f3b37',
          800: '#2c2925', 900: '#1b1917',
        },
        // 纸张色阶：角色卡 / 规则弹窗背景
        parch: {
          50: '#fffdf7', 100: '#fdf8ec', 200: '#f7eed9', 300: '#ecdcc0',
          400: '#d9c39a', 500: '#b99b6b', 600: '#8f7345', 700: '#6b552f',
        },
      },
      borderColor: {
        DEFAULT: '#e7e4dd',
      },
      boxShadow: {
        panel: '0 1px 2px rgba(28, 25, 23, 0.04), 0 8px 24px -12px rgba(28, 25, 23, 0.18)',
        float: '0 12px 40px -12px rgba(28, 25, 23, 0.32), 0 2px 8px rgba(28, 25, 23, 0.08)',
        inset: 'inset 0 1px 0 rgba(255, 255, 255, 0.6)',
        glow: '0 0 0 3px rgba(99, 102, 241, 0.16)',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        'dice-roll': 'diceShake 0.6s ease-out',
        'fade-in': 'fadeIn 0.25s ease-out',
        'slide-up': 'slideUp 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
        'slide-in-right': 'slideInRight 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
        'pop-in': 'popIn 0.22s cubic-bezier(0.22, 1, 0.36, 1)',
        'typewriter': 'blink 1s step-end infinite',
        'shimmer': 'shimmer 1.8s linear infinite',
        'pulse-soft': 'pulseSoft 1.6s ease-in-out infinite',
      },
      keyframes: {
        diceShake: {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '25%': { transform: 'rotate(-30deg) scale(1.2)' },
          '50%': { transform: 'rotate(20deg) scale(0.9)' },
          '75%': { transform: 'rotate(-10deg) scale(1.1)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        popIn: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.45' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
