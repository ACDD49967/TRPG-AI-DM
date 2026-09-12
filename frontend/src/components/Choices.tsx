/** 建议选项：DM 给出的行动候选，一点即发送 */

import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function Choices() {
  const { choices, isProcessing, sessionId } = useGameStore();

  const click = async (opt: string) => {
    if (isProcessing || !sessionId) return;
    const store = useGameStore.getState();
    store.addPlayerMessage(opt);
    store.setProcessing(true);
    store.setChoices([]);
    try {
      const r = await fetch(
        `/api/game/${sessionId}/action?username=${encodeURIComponent(useGameStore.getState().status.username || 'default')}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: opt }) },
      );
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        store.appendNarrativeText(`⚠ ${e.detail || '发送失败'}`);
        store.setProcessing(false);
      }
    } catch {
      store.appendNarrativeText('⚠ 网络错误');
      store.setProcessing(false);
    }
  };

  return (
    <AnimatePresence>
      {choices.length > 0 && !isProcessing && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          className="px-3 sm:px-4 pb-2"
        >
          <div className="mx-auto w-full max-w-3xl">
            <p className="section-label mb-1.5 px-1">建议行动</p>
            <div className="flex flex-wrap gap-2">
              {choices.map((c, i) => (
                <button
                  key={i}
                  onClick={() => click(c)}
                  className="group text-xs text-left px-3 py-2 rounded-xl border border-brand-200 bg-brand-50/70 text-brand-700
                             hover:bg-brand-100 hover:border-brand-300 hover:text-brand-800 transition-all duration-150"
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
