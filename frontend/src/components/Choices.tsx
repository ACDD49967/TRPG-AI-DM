/** 建议选项 */

import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function Choices() {
  const { choices, isProcessing, sessionId } = useGameStore();
  const click = async (opt: string) => {
    if (isProcessing || !sessionId) return;
    const store = useGameStore.getState();
    store.appendNarrativeText(`🗣️ ${opt}`); store.setProcessing(true); store.setChoices([]);
    try {
      const r = await fetch(`/api/game/${sessionId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: opt }) });
      if (!r.ok) { const e = await r.json(); store.appendNarrativeText(`⚠ ${e.detail}`); store.setProcessing(false); }
    } catch { store.appendNarrativeText('⚠ 网络错误'); store.setProcessing(false); }
  };
  return (
    <AnimatePresence>
      {choices.length > 0 && !isProcessing && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="px-5 pb-2">
          <div className="flex flex-wrap gap-2">
            {choices.map((c, i) => (
              <button key={i} onClick={() => click(c)} className="px-3 py-1.5 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 text-xs rounded-lg transition-colors">{c}</button>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
