/** 骰子动画弹窗 —— 白色简洁 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

export default function DiceRollOverlay() {
  const latest = useGameStore(s => s.latestDiceRoll);
  const [show, setShow] = useState(false);
  const [phase, setPhase] = useState<'rolling'|'result'|'hidden'>('hidden');

  useEffect(() => {
    if (latest) { setShow(true); setPhase('rolling');
      const t1 = setTimeout(() => setPhase('result'), 800);
      const t2 = setTimeout(() => { setPhase('hidden'); setTimeout(() => setShow(false), 300); }, 3000);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    } else { setShow(false); setPhase('hidden'); }
  }, [latest]);

  if (!show || !latest) return null;
  const isCrit = latest.result === '大成功' || latest.result === '大失败';
  const ok = latest.result === '成功' || latest.result === '大成功';

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <motion.div initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.5, opacity: 0 }}
          className={`rounded-2xl p-6 shadow-xl backdrop-blur-sm min-w-[260px] text-center bg-white border-2 ${
            isCrit ? (ok ? 'border-amber-400 shadow-amber-100' : 'border-red-400 shadow-red-100') :
            (ok ? 'border-emerald-300 shadow-emerald-50' : 'border-gray-300')
          }`}>
          <div className="text-5xl mb-3">
            {phase === 'rolling' ? <motion.span animate={{ rotate: [0, -30, 20, -10, 0], scale: [1, 1.2, 0.9, 1.1, 1] }} transition={{ duration: 0.8 }} className="inline-block">🎲</motion.span>
            : <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 200 }} className="inline-block">{isCrit ? (ok ? '🌟' : '💥') : (ok ? '✓' : '✗')}</motion.span>}
          </div>
          <p className="text-base font-bold text-gray-800 mb-1">{latest.skill}检定</p>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: phase === 'result' ? 1 : 0 }} className="text-2xl font-black mb-1">
            <span className={ok ? 'text-emerald-600' : 'text-red-500'}>d20 = {latest.roll}</span>
            {latest.modifier !== 0 && <span className="text-gray-400 text-lg"> +{latest.modifier} = {latest.roll + latest.modifier}</span>}
          </motion.div>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: phase === 'result' ? 1 : 0 }} className="text-xs text-gray-400 mb-2">DC {latest.dc}</motion.p>
          <motion.div initial={{ scale: 0 }} animate={{ scale: phase === 'result' ? 1 : 0 }} transition={{ type: 'spring', delay: 0.2 }}>
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${
              isCrit ? (ok ? 'bg-amber-100 text-amber-700 border border-amber-300' : 'bg-red-100 text-red-700 border border-red-300') :
              (ok ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-gray-100 text-gray-500 border border-gray-200')
            }`}>{latest.result}</span>
          </motion.div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
