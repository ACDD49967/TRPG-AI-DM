/** 职业资源（含 4e 的行动点与回复力）。没有资源且非 4e 时不渲染。 */
import type { CharacterStatus } from '../../store/gameTypes';

export default function ResourcesBlock({ status }: { status: CharacterStatus }) {
  if (!((status.class_resources?.length || 0) > 0 || status.game_system === 'dnd4e')) return null;
  return (
    <div className="mt-2 grid grid-cols-2 gap-2">
      {(status.class_resources || []).map((r, i) => (
        <details key={r.key || i} className="group bg-white/70 border border-amber-900/20 rounded-lg p-2">
          <summary className="cursor-pointer flex items-baseline justify-between">
            <p className="text-[10px] uppercase tracking-widest text-ink-500">{r.name}<span className="ml-1 group-open:hidden">▸</span></p>
            <p className="paper-title text-lg font-bold">{r.current}/{r.max}</p>
          </summary>
          {r.desc ? <p className="text-[9px] text-ink-500 mt-1 pt-1 border-t border-amber-900/10">{r.desc}</p> : null}
        </details>
      ))}
      {status.game_system === 'dnd4e' && (
        <>
          {status.bloodied && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-2">
              <div className="flex items-baseline justify-between">
                <p className="text-[10px] uppercase tracking-widest text-red-700">血竭</p>
                <p className="paper-title text-lg font-bold text-red-700">Bloodied</p>
              </div>
              <p className="text-[9px] text-red-600 mt-0.5">HP 已降到上限一半以下</p>
            </div>
          )}
          <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2">
            <div className="flex items-baseline justify-between">
              <p className="text-[10px] uppercase tracking-widest text-ink-500">行动点</p>
              <p className="paper-title text-lg font-bold">{status.action_points ?? 1}</p>
            </div>
            <p className="text-[9px] text-ink-500 mt-0.5">长休重置为 1，里程碑 +1</p>
          </div>
          <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2">
            <div className="flex items-baseline justify-between">
              <p className="text-[10px] uppercase tracking-widest text-ink-500">回复力</p>
              <p className="paper-title text-lg font-bold">{status.healing_surges ?? 0}/{status.max_healing_surges ?? 0}</p>
            </div>
            <p className="text-[9px] text-ink-500 mt-0.5">每次回复 {status.surge_value ?? 0} HP</p>
          </div>
        </>
      )}
    </div>
  );
}
