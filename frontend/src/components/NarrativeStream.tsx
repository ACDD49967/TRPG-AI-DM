/** 叙事流 —— 白色简洁打字机 */

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

/** 渲染一段叙事文本，处理分段和格式化 */
function NarrativeBlock({ text }: { text: string }) {
  // 按空行分段，每段独立渲染
  const paragraphs = text.split(/\n\s*\n/).filter(p => p.trim());
  if (paragraphs.length <= 1) {
    // 单段：保留换行但作为 <br>
    return <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{text}</p>;
  }
  return (
    <div className="space-y-2">
      {paragraphs.map((p, i) => (
        <p key={i} className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{p.trim()}</p>
      ))}
    </div>
  );
}

export default function NarrativeStream() {
  const { narrative, currentTokenBuffer, isProcessing } = useGameStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [narrative, currentTokenBuffer]);

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-4 min-h-0">
      {narrative.length === 0 && !currentTokenBuffer && (
        <div className="text-center text-gray-300 py-20">
          <p className="text-3xl mb-2">🗡️</p>
          <p className="text-sm text-gray-400">等待游戏开始...</p>
        </div>
      )}

      <AnimatePresence>
        {narrative.map((line) => (
          <motion.div key={line.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
            className={`${
              line.isDiceRoll ? 'bg-indigo-50 border border-indigo-100 rounded-lg p-2.5' :
              line.isGameEvent ? 'bg-amber-50 border border-amber-100 rounded-lg p-2.5' :
              ''
            }`}
          >
            {line.isDiceRoll && line.diceData && <DiceBadge data={line.diceData} />}
            {line.isGameEvent && line.gameEventData && (
              <div><span className="font-bold text-amber-600">{line.gameEventData.type === 'combat' ? '⚔️ 战斗' : '📜 事件'}</span><p className="mt-1 text-sm text-amber-700">{line.gameEventData.description}</p></div>
            )}
            {!line.isDiceRoll && !line.isGameEvent && <NarrativeBlock text={line.text} />}
          </motion.div>
        ))}
      </AnimatePresence>

      {currentTokenBuffer && <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{currentTokenBuffer}<span className="text-indigo-400 animate-pulse">▎</span></p>}
      {isProcessing && !currentTokenBuffer && narrative.length > 0 && <div className="flex items-center gap-2 text-indigo-400 text-xs"><span className="animate-pulse">●</span>主持正在思考...</div>}
      <div ref={bottomRef} />
    </div>
  );
}

function DiceBadge({ data }: { data: { skill: string; dc: number; roll: number; modifier: number; result: string } }) {
  const isCrit = data.result === '大成功' || data.result === '大失败';
  const ok = data.result === '成功' || data.result === '大成功';
  return (
    <div className="flex items-center gap-2 flex-wrap mb-1">
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${isCrit?(ok?'bg-amber-100 text-amber-700 border border-amber-200':'bg-red-100 text-red-700 border border-red-200'):(ok?'bg-emerald-100 text-emerald-700 border border-emerald-200':'bg-gray-100 text-gray-500 border border-gray-200')}`}>{isCrit?(ok?'🌟':'💥'):(ok?'✓':'✗')} {data.result}</span>
      <span className="text-xs text-gray-500">{data.skill}: <span className="font-bold text-gray-700">d20={data.roll}</span>{data.modifier!==0&&<span>+{data.modifier}</span>} <span className="text-gray-400">vs DC{data.dc}</span></span>
    </div>
  );
}
