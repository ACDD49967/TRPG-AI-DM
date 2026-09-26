/** 战场态势与先攻顺序（顺序由后端维护，前端只展示）（从 StatusPanel 拆出；只做展示，数据由父组件传入）。 */
import type { BattlefieldPlacement, InitiativeState } from '../../store/gameStore';

// 后端 battlefield.py 的档位/掩体枚举 → 玩家可读文案（跟着区块搬过来）
const BAND_LABELS: Record<string, string> = {
  engaged: '缠斗', near: '近距离', far: '远距离', out: '脱离交战',
};
const COVER_LABELS: Record<string, string> = {
  none: '无掩体', half: '半掩体 +2', three_quarters: '四分之三掩体 +5', full: '全掩体',
};

export default function TacticalBlock({ placements, initiative }: {
  placements: BattlefieldPlacement[];
  initiative: InitiativeState | null;
}) {
  return (
    <>
        {placements.length > 0 && (
          <div className="rounded-xl bg-stone-50 border border-stone-200 p-2.5">
            <p className="text-2xs text-stone-600 font-medium mb-1">战场态势</p>
            <div className="space-y-1">
              {placements.map((p) => (
                <div key={p.name} className="flex items-center justify-between gap-2">
                  <span className="text-2xs text-stone-700 truncate">
                    {p.name}
                    {p.note ? <span className="text-ink-400">（{p.note}）</span> : null}
                  </span>
                  <span className="text-3xs text-stone-500 shrink-0">
                    {BAND_LABELS[p.band] || p.band || '—'} · {COVER_LABELS[p.cover] || p.cover || '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {initiative && initiative.order.length > 0 && (
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-2.5">
            <p className="text-2xs text-slate-600 font-bold flex items-center justify-between mb-1">
              <span>先攻顺序</span>
              <span className="font-mono text-ink-400">第 {initiative.round} 轮</span>
            </p>
            <div className="space-y-1">
              {initiative.order.map((c) => (
                <div key={c.name} className="flex items-center justify-between gap-2">
                  <span
                    className={`text-2xs truncate ${
                      !c.alive
                        ? 'text-ink-300 line-through'
                        : c.is_player
                          ? 'text-brand-700 font-medium'
                          : 'text-slate-700'
                    }`}
                  >
                    {c.is_current && c.alive ? '▶ ' : ''}
                    {c.name}
                    {c.turns_left > 1 ? `（余 ${c.turns_left} 回合）` : ''}
                  </span>
                  <span className="text-2xs font-mono text-ink-400 shrink-0">{c.initiative}</span>
                </div>
              ))}
            </div>
          </div>
        )}
    </>
  );
}
