/** DM决策建议面板 */

import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function DecisionPanel() {
  const { decisionSuggestions, isProcessing, sessionId } = useGameStore();
  if (decisionSuggestions.length === 0 || isProcessing) return null;

  const click = async (s: string) => {
    const store = useGameStore.getState();
    if (!sessionId || store.isProcessing) return;
    store.appendNarrativeText(`你说：${s}`); store.setProcessing(true); store.setDecisionSuggestions([]);
    try {
      const r = await fetch(`/api/game/${sessionId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: s }) });
      if (!r.ok) { const e = await r.json(); store.appendNarrativeText(`错误：${e.detail}`); store.setProcessing(false); }
    } catch { store.appendNarrativeText('错误：网络错误'); store.setProcessing(false); }
  };

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="px-5 pb-2">
        <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-3">
          <p className="text-[10px] text-indigo-600 font-medium mb-2">决策建议</p>
          <div className="flex flex-wrap gap-2">
            {decisionSuggestions.map((s, i) => (
              <button key={i} onClick={() => click(s)} className="text-xs px-3 py-1.5 bg-white border border-indigo-200 hover:bg-indigo-50 text-indigo-700 rounded-lg transition-colors text-left">{s}</button>
            ))}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
