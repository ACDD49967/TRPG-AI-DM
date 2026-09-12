/**
 * 叙事流 —— 阅读为主的正文区
 *
 * 优化点：
 *  - 正文按「阅读栏宽度」约束（max-w-3xl）并加大字号/行高，长段落不再贴边。
 *  - 主持人叙事与玩家发言视觉分离：DM 用带标记的段落，玩家用气泡。
 *  - 骰子/事件行改为紧凑横幅，保留数值过程但不打断叙事节奏。
 *  - 新增「回到底部」按钮：向上翻阅历史后自动出现，无需手动滚回。
 *  - 处理中状态提供可见反馈（思考中 / 打字光标），避免玩家以为卡死。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

/** 轻量 Markdown 内联渲染：粗体/斜体/删除线 */
function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-ink-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic text-ink-700">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('~~') && part.endsWith('~~')) {
      return <span key={i} className="line-through text-ink-400">{part.slice(2, -2)}</span>;
    }
    return <span key={i}>{part}</span>;
  });
}

/** 渲染一段叙事文本，支持 Markdown 常见块级结构 */
function NarrativeBlock({ text }: { text: string }) {
  const paragraphs = text.replace(/\r\n/g, '\n').split(/\n\s*\n/).filter((p) => p.trim());
  return (
    <div className="narrative-prose">
      {paragraphs.map((p, i) => {
        const trimmed = p.trim();
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
          return <hr key={i} className="my-3 border-ink-200" />;
        }
        if (trimmed.startsWith('### ')) {
          return <h4 key={i} className="text-sm font-bold text-ink-900 mt-1 mb-1.5">{renderInline(trimmed.slice(4))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={i} className="text-base font-bold text-ink-900 mt-1 mb-1.5">{renderInline(trimmed.slice(3))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={i} className="text-lg font-bold text-ink-900 mt-1 mb-2">{renderInline(trimmed.slice(2))}</h2>;
        }
        const lines = trimmed.split('\n');

        // 引用块
        if (lines.every((l) => /^\s*>\s?/.test(l))) {
          return (
            <blockquote
              key={i}
              className="border-l-[3px] border-brand-300 bg-brand-50/60 rounded-r-xl px-3.5 py-2.5 text-ink-600 text-sm leading-relaxed mb-3"
            >
              {lines.map((l, j) => (
                <p key={j} className={j > 0 ? 'mt-1' : ''}>{renderInline(l.replace(/^\s*>\s?/, ''))}</p>
              ))}
            </blockquote>
          );
        }

        // 无序列表
        if (lines.every((l) => /^\s*[-*+]\s+/.test(l))) {
          return (
            <ul key={i} className="space-y-1 pl-5 list-disc marker:text-ink-400 mb-3">
              {lines.map((l, j) => (
                <li key={j} className="text-ink-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*[-*+]\s+/, ''))}</li>
              ))}
            </ul>
          );
        }

        // 有序列表
        if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
          return (
            <ol key={i} className="space-y-1 pl-5 list-decimal marker:text-ink-400 mb-3">
              {lines.map((l, j) => (
                <li key={j} className="text-ink-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*\d+[.)]\s+/, ''))}</li>
              ))}
            </ol>
          );
        }

        // 简易表格：至少两行，且第二行是分隔行
        const tableLines = lines.filter((l) => l.includes('|'));
        if (tableLines.length >= 2 && /^\s*\|?[\s:|-]+\|?\s*$/.test(tableLines[1])) {
          const parseRow = (row: string) => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
          const head = parseRow(tableLines[0]);
          const body = tableLines.slice(2);
          return (
            <div key={i} className="mb-3 overflow-x-auto border border-ink-200 rounded-xl">
              <table className="w-full text-left text-xs">
                <thead className="bg-ink-50">
                  <tr>
                    {head.map((h, j) => (
                      <th key={j} className="px-2.5 py-2 font-semibold text-ink-700 border-b border-ink-200 whitespace-nowrap">{renderInline(h)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, r) => (
                    <tr key={r} className="even:bg-ink-50/40">
                      {parseRow(row).map((c, j) => (
                        <td key={j} className="px-2.5 py-2 text-ink-600 border-b border-ink-100 last:border-0">{renderInline(c)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return (
          <p key={i} className="mb-3 last:mb-0 whitespace-pre-line">{renderInline(trimmed)}</p>
        );
      })}
    </div>
  );
}

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

function DiceBadge({ data }: { data: { skill: string; dc: number; roll: number; modifier: number; result: string } }) {
  const ok = ['成功', '大成功', '困难成功', '极限成功', '复活'].includes(data.result);
  const isCrit = ['大成功', '大失败'].includes(data.result) || data.result === '复活';
  const badgeCls = isCrit
    ? ok
      ? 'bg-amber-100 text-amber-700 border-amber-300'
      : 'bg-red-100 text-red-700 border-red-300'
    : ok
      ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
      : 'bg-ink-100 text-ink-500 border-ink-200';
  return (
    <div className="flex items-center gap-2.5 flex-wrap w-fit max-w-full rounded-xl border border-brand-200/70 bg-brand-50/70 px-3.5 py-2.5">
      <span className={`text-2xs font-semibold px-2 py-0.5 rounded-full border ${badgeCls}`}>{data.result}</span>
      <span className="text-xs text-ink-600">
        {data.skill}：<span className="font-mono font-bold text-ink-800">d20={data.roll}</span>
        {data.modifier !== 0 && <span className="font-mono"> {data.modifier > 0 ? `+${data.modifier}` : data.modifier}</span>}
        <span className="text-ink-500"> vs DC{data.dc}</span>
      </span>
    </div>
  );
}
