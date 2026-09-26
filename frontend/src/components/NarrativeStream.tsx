/**
 * 叙事流：自动滚动到底、上滑时暂停跟随，并按消息类型渲染
 * （叙事正文 / 骰子徽章 / 游戏事件 / 系统提示）。
 *
 * 正文渲染与骰子徽章拆到 `narrative/`；这里只留滚动与列表编排。
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';
import DiceBadge from './narrative/DiceBadge';
import NarrativeBlock from './narrative/NarrativeBlock';


export default function NarrativeStream() {
  const { narrative, currentTokenBuffer, isProcessing } = useGameStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  const lastId = useMemo(() => narrative[narrative.length - 1]?.id, [narrative]);

  // 只有玩家停在底部时才自动跟随，避免打断向上翻阅历史
  useEffect(() => {
    if (pinned) bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [lastId, currentTokenBuffer, pinned]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setPinned(distance < 80);
  };

  const scrollToBottom = () => {
    setPinned(true);
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  };

  const empty = narrative.length === 0 && !currentTokenBuffer;

  return (
    <div className="relative flex-1 min-h-0 flex flex-col">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 min-h-0"
      >
        <div className="mx-auto w-full max-w-3xl space-y-4">
          {empty && (
            <div className="text-center text-ink-300 py-16 sm:py-24">
              <p className="text-4xl font-black tracking-[0.2em] text-ink-200 mb-3">TRPG</p>
              <p className="text-xs text-ink-400">等待游戏开始…</p>
            </div>
          )}

          <AnimatePresence initial={false}>
            {narrative.map((line) => {
              if (line.role === 'player') {
                return (
                  <motion.div
                    key={line.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex justify-end"
                  >
                    <div className="bubble-player">
                      <p className="text-2xs text-brand-500 font-semibold mb-1">你</p>
                      <p className="text-sm text-ink-800 whitespace-pre-line leading-relaxed">{line.text}</p>
                    </div>
                  </motion.div>
                );
              }
              return (
                <motion.div
                  key={line.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {line.isDiceRoll && line.diceData && <DiceBadge data={line.diceData} />}
                  {line.isGameEvent && line.gameEventData && (
                    <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/80 px-3.5 py-2.5">
                      <span className="shrink-0 mt-px text-2xs font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                        {line.gameEventData.type === 'combat' ? '战斗' : '事件'}
                      </span>
                      <p className="text-sm text-amber-800 leading-relaxed">{line.gameEventData.description}</p>
                    </div>
                  )}
                  {!line.isDiceRoll && !line.isGameEvent && <NarrativeBlock text={line.text} />}
                </motion.div>
              );
            })}
          </AnimatePresence>

          {currentTokenBuffer && (
            <p className="narrative-prose whitespace-pre-line">
              {currentTokenBuffer}
              <span className="text-brand-500 animate-pulse">▎</span>
            </p>
          )}

          {isProcessing && !currentTokenBuffer && narrative.length > 0 && (
            <div className="flex items-center gap-2 text-brand-600 text-xs" aria-live="polite">
              <span className="flex gap-1" aria-hidden>
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft" />
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft [animation-delay:0.4s]" />
              </span>
              主持正在思考…
            </div>
          )}

          <div ref={bottomRef} className="h-px" />
        </div>
      </div>

      {/* 向上翻阅历史后浮现的回到最新按钮 */}
      <AnimatePresence>
        {!pinned && !empty && (
          <motion.button
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            onClick={scrollToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 inline-flex items-center gap-1.5 rounded-full
                       bg-ink-800/90 text-white text-2xs px-3.5 py-2 shadow-float backdrop-blur
                       hover:bg-ink-900 transition-colors"
          >
            <svg viewBox="0 0 20 20" fill="none" className="w-3.5 h-3.5" aria-hidden>
              <path d="M10 4v12m0 0l-5-5m5 5l5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            回到最新
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
