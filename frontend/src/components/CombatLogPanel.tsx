/** 战斗记录独立面板 —— 统一展示骰子判定、玩家攻击、敌人回合 */

import { useEffect, useRef, useState } from 'react';
import { useGameStore } from '../store/gameStore';

const KIND_META = {
  enemy: { icon: '敌', cls: 'bg-red-50 text-red-700 border-red-200', label: '敌人回合' },
  dice: { icon: '骰', cls: 'bg-brand-50 text-brand-600 border-brand-200', label: '骰子判定' },
  combat: { icon: '战', cls: 'bg-amber-50 text-amber-700 border-amber-200', label: '玩家行动' },
} as const;

export default function CombatLogPanel() {
  const combatLog = useGameStore((s) => s.combatLog);
  const clearCombatLog = useGameStore((s) => s.clearCombatLog);
  // 窄屏默认折叠：手机上固定区每多占 40px，叙事就少一行
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);
  const listRef = useRef<HTMLDivElement>(null);

  // 新记录到达时自动滚到底部，战斗中不必手动下拉
  useEffect(() => {
    if (!collapsed && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [combatLog.length, collapsed]);

  if (combatLog.length === 0 && collapsed) return null;

  return (
    <div className="border-t border-ink-200 bg-white/70 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center justify-between gap-2 px-4 py-1.5 mx-auto w-full max-w-3xl">
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center gap-2 min-h-[28px] text-xs font-bold text-ink-600 hover:text-ink-900 transition-colors"
          aria-expanded={!collapsed}
        >
          <span aria-hidden>⚔️</span>
          战斗记录
          {combatLog.length > 0 && (
            <span className="text-2xs font-mono px-1.5 py-0.5 rounded-full bg-ink-100 text-ink-500">{combatLog.length}</span>
          )}
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className={`w-3.5 h-3.5 text-ink-400 transition-transform duration-200 ${collapsed ? '-rotate-90' : ''}`}
            aria-hidden
          >
            <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {combatLog.length > 0 && (
          <button onClick={clearCombatLog} className="text-2xs text-ink-400 hover:text-red-700 transition-colors min-h-[28px] px-2 -my-1 rounded-lg hover:bg-ink-50">
            清空
          </button>
        )}
      </div>

      {!collapsed && (
        <div
          ref={listRef}
          className="max-h-24 sm:max-h-40 overflow-y-auto px-4 pb-3 space-y-2 border-t border-ink-100 pt-2.5 mx-auto w-full max-w-3xl"
        >
          {combatLog.length === 0 ? (
            <p className="text-2xs text-ink-400 py-3 text-center">暂无战斗记录</p>
          ) : (
            combatLog.map((entry) => {
              const meta = KIND_META[entry.kind] || KIND_META.combat;
              return (
                <div key={entry.id} className="flex items-start gap-2.5">
                  <span
                    className={`shrink-0 mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center text-2xs font-bold border ${meta.cls}`}
                    title={meta.label}
                    aria-label={meta.label}
                  >
                    {meta.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-ink-700 whitespace-pre-line leading-relaxed">{entry.text}</p>
                    <p className="text-3xs text-ink-500 font-mono mt-0.5">{entry.time}</p>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
