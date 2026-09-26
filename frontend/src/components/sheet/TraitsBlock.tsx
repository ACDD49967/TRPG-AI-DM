/** 种族特性 / 职业熟练 / 专长 / 背景特征。三者都空时不渲染。 */
import type { CharacterStatus } from '../../store/gameTypes';

export default function TraitsBlock({ status }: { status: CharacterStatus }) {
  if (!(status.race_traits?.length || status.feats?.length || status.class_proficiencies?.length)) return null;
  return (
    <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
      <p className="section-label mb-1">特性 / 特长 / 背景特征</p>
      <div className="space-y-1">
        {(status.race_traits || []).map((t, i) => <p key={i} className="text-[10px] text-ink-600">· {t}</p>)}
        {(status.class_proficiencies || []).map((t, i) => <p key={i} className="text-[10px] text-ink-600">· {t}</p>)}
        {(status.feats || []).map((f, i) => <p key={i} className="text-[10px] text-amber-800">· {f.name}</p>)}
      </div>
    </div>
  );
}
