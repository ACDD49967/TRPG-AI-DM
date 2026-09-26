/** 职业资源 / 法术位 / 已习得法术摘要（从 StatusPanel 拆出；只做展示，数据由父组件传入）。 */
import type { CharacterStatus } from '../../store/gameStore';

export default function ResourceBlock({ system, status, spellSlots }: {
  system: string;
  status: CharacterStatus;
  spellSlots: string[];
}) {
  return (
    <>
        {/* 职业资源 / 法术位 */}
        {((status.class_resources?.length || 0) > 0 || spellSlots.length > 0 || system === 'dnd4e') && (
          <div className="pt-2 border-t border-ink-100">
            <p className="section-label mb-1.5">职业资源</p>
            <div className="space-y-1">
              {(status.class_resources || []).slice(0, 4).map((r) => (
                <div key={r.key} className="flex items-center justify-between bg-ink-50 rounded-lg px-2 py-1 border border-ink-200">
                  <span className="text-ink-600 text-2xs truncate">{r.name}</span>
                  <span className="text-ink-800 font-mono font-semibold text-2xs">
                    {r.current}/{r.max}
                  </span>
                </div>
              ))}
              {spellSlots.length > 0 && (
                <p className="text-3xs text-ink-400">法术位 {spellSlots.join(' ')}</p>
              )}
              {system === 'dnd4e' && <p className="text-3xs text-ink-400">行动点 {status.action_points ?? 1}</p>}
            </div>
          </div>
        )}

        {/* 已习得法术摘要 */}
        {((status.known_spells?.length || 0) > 0) && (
          <div className="pt-2 border-t border-ink-100">
            <p className="section-label mb-1.5">已习得法术（{status.known_spells!.length}）</p>
            <div className="space-y-1">
              {status.known_spells!.slice(0, 5).map((s) => (
                <div key={s.name} className="text-2xs text-ink-600 bg-white border border-ink-200 rounded-lg px-2 py-1 truncate">
                  {s.name}：{Number(s.level) === 0 ? '戏法' : `${s.level}环`} {s.school}
                </div>
              ))}
              {status.known_spells!.length > 5 && (
                <p className="text-3xs text-ink-400">…还有 {status.known_spells!.length - 5} 个</p>
              )}
            </div>
          </div>
        )}
    </>
  );
}
