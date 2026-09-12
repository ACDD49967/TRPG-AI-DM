/** 骰子动画弹窗 —— 非阻塞展示检定结果，3 秒后自动淡出 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function DiceRollOverlay() {
  const latest = useGameStore((s) => s.latestDiceRoll);
  const [show, setShow] = useState(false);
  const [phase, setPhase] = useState<'rolling' | 'result' | 'hidden'>('hidden');

  useEffect(() => {
    if (latest) {
      setShow(true);
      setPhase('rolling');
      const t1 = setTimeout(() => setPhase('result'), 800);
      const t2 = setTimeout(() => {
        setPhase('hidden');
        setTimeout(() => setShow(false), 300);
      }, 3000);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }
    setShow(false);
    setPhase('hidden');
  }, [latest]);

  if (!show || !latest) return null;
  const ok = ['成功', '大成功', '困难成功', '极限成功', '复活'].includes(latest.result);
  const isCrit = ['大成功', '大失败'].includes(latest.result) || latest.result === '复活';

  // 大成功/大失败用更强的视觉层级，普通成败保持克制
  const accent = isCrit
    ? ok
      ? { ring: 'border-amber-400', glow: 'shadow-[0_0_60px_-12px_rgba(245,158,11,0.65)]', text: 'text-amber-700' }
      : { ring: 'border-red-400', glow: 'shadow-[0_0_60px_-12px_rgba(239,68,68,0.6)]', text: 'text-red-600' }
    : ok
      ? { ring: 'border-emerald-300', glow: 'shadow-float', text: 'text-emerald-600' }
      : { ring: 'border-ink-300', glow: 'shadow-float', text: 'text-ink-500' };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[90] flex items-center justify-center pointer-events-none p-4"
        aria-live="polite"
      >
        <motion.div
          initial={{ scale: 0.85, opacity: 0, y: 8 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 22 }}
          className={`rounded-3xl px-7 py-6 min-w-[240px] max-w-xs text-center bg-white/95 backdrop-blur
                      border-2 ${accent.ring} ${accent.glow}`}
        >
          <div className="h-14 flex items-center justify-center mb-1">
            {phase === 'rolling' ? (
              <motion.span
                animate={{ rotate: [0, -30, 20, -10, 0], scale: [1, 1.15, 0.92, 1.08, 1] }}
                transition={{ duration: 0.8 }}
                className="inline-block font-black text-2xl text-ink-300 tracking-tight"
                aria-hidden
              >
                D20
              </motion.span>
            ) : (
              <motion.span
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 260, damping: 18 }}
                className={`inline-block text-2xl font-black ${accent.text}`}
              >
                {latest.result}
              </motion.span>
            )}
          </div>

          <p className="text-sm font-bold text-ink-700 mb-1.5">{latest.skill}检定</p>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: phase === 'result' ? 1 : 0.25 }}
            className="text-xl font-black font-mono mb-1"
          >
            <span className={ok ? 'text-emerald-600' : 'text-red-700'}>{latest.roll}</span>
            {latest.modifier !== 0 && (
              <span className="text-ink-400 text-base">
                {' '}
                {latest.modifier > 0 ? `+${latest.modifier}` : latest.modifier} = {latest.roll + latest.modifier}
              </span>
            )}
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: phase === 'result' ? 1 : 0 }}
            className="text-2xs text-ink-400 font-mono"
          >
            DC {latest.dc}
          </motion.p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
