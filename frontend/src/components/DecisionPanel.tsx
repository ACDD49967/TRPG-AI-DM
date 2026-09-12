/** DM 决策建议面板：把「下一步可以做什么」以明确卡片形式给出 */

import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function DecisionPanel() {
  const { decisionSuggestions, isProcessing, sessionId } = useGameStore();
  if (decisionSuggestions.length === 0 || isProcessing) return null;

  const click = async (s: string) => {
    const store = useGameStore.getState();
    if (!sessionId || store.isProcessing) return;
    store.addPlayerMessage(s);
    store.setProcessing(true);
    store.setDecisionSuggestions([]);
    try {
      const r = await fetch(
        `/api/game/${sessionId}/action?username=${encodeURIComponent(useGameStore.getState().status.username || 'default')}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: s }) },
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
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="px-3 sm:px-4 pb-2"
      >
        <div className="mx-auto w-full max-w-3xl">
          {/* 与「建议行动」刻意区分：DM 提示是顾问性质（虚线、琥珀色），
              建议行动是主操作（实线、品牌色），避免两组 chip 抢戏 */}
          <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50/50 px-3 py-2.5">
            <p className="section-label text-amber-700 mb-2 flex items-center gap-1.5">
              <span aria-hidden>💡</span> DM 提示（可直接采用）
            </p>
            <div className="flex flex-wrap gap-2">
              {decisionSuggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => click(s)}
                  className="text-xs text-left px-3 py-2 rounded-xl border border-amber-200 bg-white/80 text-amber-800
                             hover:bg-amber-100 hover:border-amber-300 transition-all duration-150"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
