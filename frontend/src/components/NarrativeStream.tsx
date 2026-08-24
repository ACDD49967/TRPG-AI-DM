/** 叙事流 —— 白色简洁打字机 */

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

/** 轻量 Markdown 内联渲染：粗体/斜体/删除线 */
function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic text-gray-800">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('~~') && part.endsWith('~~')) {
      return <span key={i} className="line-through text-gray-400">{part.slice(2, -2)}</span>;
    }
    return <span key={i}>{part}</span>;
  });
}

/** 渲染一段叙事文本，支持 Markdown 常见块级结构 */
function NarrativeBlock({ text }: { text: string }) {
  const paragraphs = text.replace(/\r\n/g, '\n').split(/\n\s*\n/).filter(p => p.trim());
  return (
    <div className="space-y-2">
      {paragraphs.map((p, i) => {
        const trimmed = p.trim();
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
          return <hr key={i} className="border-gray-200 my-2" />;
        }
        if (trimmed.startsWith('### ')) {
          return <h4 key={i} className="text-sm font-bold text-gray-900 mt-1">{renderInline(trimmed.slice(4))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={i} className="text-base font-bold text-gray-900 mt-1">{renderInline(trimmed.slice(3))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={i} className="text-lg font-bold text-gray-900 mt-1">{renderInline(trimmed.slice(2))}</h2>;
        }
        const lines = trimmed.split('\n');

        // 引用块
        if (lines.every(l => /^\s*>\s?/.test(l))) {
          return (
            <blockquote key={i} className="border-l-4 border-indigo-200 bg-indigo-50/50 rounded-r-lg px-3 py-1.5 text-gray-600 text-sm leading-relaxed">
              {lines.map((l, j) => <p key={j} className={j > 0 ? 'mt-1' : ''}>{renderInline(l.replace(/^\s*>\s?/, ''))}</p>)}
            </blockquote>
          );
        }

        // 无序列表
        if (lines.every(l => /^\s*[-*+]\s+/.test(l))) {
          return (
            <ul key={i} className="space-y-1 pl-4 list-disc marker:text-gray-400">
              {lines.map((l, j) => <li key={j} className="text-gray-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*[-*+]\s+/, ''))}</li>)}
            </ul>
          );
        }

        // 有序列表
        if (lines.every(l => /^\s*\d+[.)]\s+/.test(l))) {
          return (
            <ol key={i} className="space-y-1 pl-4 list-decimal marker:text-gray-400">
              {lines.map((l, j) => <li key={j} className="text-gray-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*\d+[.)]\s+/, ''))}</li>)}
            </ol>
          );
        }

        // 简易表格：至少两行，且第二行是分隔行
        const tableLines = lines.filter(l => l.includes('|'));
        if (tableLines.length >= 2 && /^\s*\|?[\s:|-]+\|?\s*$/.test(tableLines[1])) {
          const parseRow = (row: string) => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
          const head = parseRow(tableLines[0]);
          const body = tableLines.slice(2);
          return (
            <div key={i} className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50">
                  <tr>{head.map((h, j) => <th key={j} className="px-2.5 py-1.5 font-semibold text-gray-700 border-b border-gray-200">{renderInline(h)}</th>)}</tr>
                </thead>
                <tbody>
                  {body.map((row, r) => (
                    <tr key={r} className="even:bg-gray-50/50">
                      {parseRow(row).map((c, j) => <td key={j} className="px-2.5 py-1.5 text-gray-600 border-b border-gray-100 last:border-0">{renderInline(c)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return <p key={i} className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{renderInline(trimmed)}</p>;
      })}
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
          <p className="text-3xl font-black text-gray-300 mb-2">TRPG</p>
          <p className="text-sm text-gray-400">等待游戏开始...</p>
        </div>
      )}

      <AnimatePresence>
        {narrative.map((line) => {
          if (line.role === 'player') {
            return (
              <motion.div key={line.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
                className="flex justify-end"
              >
                <div className="max-w-[85%] bg-indigo-50 border border-indigo-100 rounded-2xl rounded-br-sm px-3 py-2">
                  <p className="text-[9px] text-indigo-400 font-medium mb-0.5">你</p>
                  <p className="text-sm text-gray-800 whitespace-pre-line leading-relaxed">{line.text}</p>
                </div>
              </motion.div>
            );
          }
          return (
            <motion.div key={line.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
              className={`${
                line.isDiceRoll ? 'bg-indigo-50 border border-indigo-100 rounded-lg p-2.5' :
                line.isGameEvent ? 'bg-amber-50 border border-amber-100 rounded-lg p-2.5' :
                ''
              }`}
            >
              {line.isDiceRoll && line.diceData && <DiceBadge data={line.diceData} />}
              {line.isGameEvent && line.gameEventData && (
                <div><span className="font-bold text-amber-600">{line.gameEventData.type === 'combat' ? '战斗' : '事件'}</span><p className="mt-1 text-sm text-amber-700">{line.gameEventData.description}</p></div>
              )}
              {!line.isDiceRoll && !line.isGameEvent && <NarrativeBlock text={line.text} />}
            </motion.div>
          );
        })}
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
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${isCrit?(ok?'bg-amber-100 text-amber-700 border border-amber-200':'bg-red-100 text-red-700 border border-red-200'):(ok?'bg-emerald-100 text-emerald-700 border border-emerald-200':'bg-gray-100 text-gray-500 border border-gray-200')}`}>{data.result}</span>
      <span className="text-xs text-gray-500">{data.skill}: <span className="font-bold text-gray-700">d20={data.roll}</span>{data.modifier!==0&&<span>+{data.modifier}</span>} <span className="text-gray-400">vs DC{data.dc}</span></span>
    </div>
  );
}
