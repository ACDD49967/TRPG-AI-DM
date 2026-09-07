/** 战斗记录独立面板 —— 统一展示骰子判定、玩家攻击、敌人回合 */

import { useState } from 'react';
import { useGameStore } from '../store/gameStore';

export default function CombatLogPanel() {
  const combatLog = useGameStore((s) => s.combatLog);
  const clearCombatLog = useGameStore((s) => s.clearCombatLog);
  const [collapsed, setCollapsed] = useState(false);

  if (combatLog.length === 0 && collapsed) return null;

  return (
    <div className="border-t border-gray-200 bg-white/70 backdrop-blur-sm">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-100">
        <button onClick={() => setCollapsed((v) => !v)} className="text-xs font-bold text-gray-600 hover:text-gray-900 flex items-center gap-1">
          <span className="text-red-500">⚔️</span> 战斗记录
          <span className="text-[9px] text-gray-400">{combatLog.length}</span>
          <span className="text-[9px] text-gray-300">{collapsed ? '展开' : '收起'}</span>
        </button>
        {combatLog.length > 0 && (
          <button onClick={clearCombatLog} className="text-[9px] text-gray-400 hover:text-red-500">清空</button>
        )}
      </div>
      {!collapsed && (
        <div className="max-h-36 overflow-y-auto px-3 py-2 space-y-1.5">
          {combatLog.length === 0 ? (
            <p className="text-[10px] text-gray-300 py-2 text-center">暂无战斗记录</p>
          ) : (
            combatLog.map((entry) => (
              <div key={entry.id} className="flex items-start gap-2 text-[11px] leading-snug">
                <span className={`shrink-0 mt-0.5 w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold ${
                  entry.kind === 'enemy' ? 'bg-red-50 text-red-600 border border-red-100' :
                  entry.kind === 'dice' ? 'bg-indigo-50 text-indigo-600 border border-indigo-100' :
                  'bg-amber-50 text-amber-700 border border-amber-100'
                }`}>
                  {entry.kind === 'enemy' ? '敌' : entry.kind === 'dice' ? '骰' : '战'}
                </span>
                <div className="min-w-0">
                  <p className="text-gray-600 whitespace-pre-line">{entry.text}</p>
                  <p className="text-[9px] text-gray-300">{entry.time}</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
