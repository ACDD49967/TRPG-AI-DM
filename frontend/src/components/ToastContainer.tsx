/** 全局 Toast 容器 —— 图标 + 可关闭 + 无障碍播报 */

import { motion, AnimatePresence } from 'framer-motion';
import { useToastStore } from '../store/toastStore';

const TONES = {
  info: { cls: 'border-brand-200', icon: 'ℹ', iconCls: 'bg-brand-100 text-brand-600' },
  success: { cls: 'border-emerald-200', icon: '✓', iconCls: 'bg-emerald-100 text-emerald-600' },
  error: { cls: 'border-red-200', icon: '!', iconCls: 'bg-red-100 text-red-600' },
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();
  return (
    <div
      className="fixed z-[120] bottom-4 left-1/2 -translate-x-1/2 flex flex-col-reverse items-center gap-2 pointer-events-none px-3 w-full max-w-md sm:left-auto sm:right-4 sm:translate-x-0 sm:items-end"
      role="status"
      aria-live="polite"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const tone = TONES[t.type] || TONES.info;
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 14, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className={`pointer-events-auto w-full sm:w-auto flex items-start gap-2.5 rounded-xl border bg-white shadow-float px-3.5 py-2.5 text-xs text-ink-700 ${tone.cls}`}
            >
              <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${tone.iconCls}`} aria-hidden>
                {tone.icon}
              </span>
              <span className="flex-1 min-w-0 leading-relaxed">{t.message}</span>
              <button
                onClick={() => removeToast(t.id)}
                className="shrink-0 -mr-1 w-5 h-5 rounded-md text-ink-400 hover:text-ink-700 hover:bg-ink-100 flex items-center justify-center transition-colors"
                aria-label="关闭提示"
              >
                <svg viewBox="0 0 20 20" fill="none" className="w-3 h-3" aria-hidden>
                  <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
