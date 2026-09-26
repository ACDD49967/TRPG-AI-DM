/** 六维属性 + 熟练豁免 + 熟练技能明细。 */
import type { CharacterStatus } from '../../store/gameTypes';
import { ATTR_CN, SKILL_ATTR, mod } from './helpers';

export default function AbilitiesBlock({ status, attrs, keys, prof, skillProf }: {
  status: CharacterStatus;
  attrs: Record<string, number>;
  keys: string[];
  prof: number;
  skillProf: string[];
}) {
  return (
    <>
      {/* 六维属性 */}
      <div className="mt-4">
        <p className="section-label mb-2">属性</p>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {keys.map(k => {
            const v = Number(attrs[k] ?? 10);
            return (
              <div key={k} className="bg-white border-2 border-amber-900/30 rounded-lg py-2 text-center shadow-sm">
                <p className="text-[9px] uppercase tracking-widest text-ink-400">{ATTR_CN[k]}</p>
                <p className="paper-title text-2xl font-black">{mod(v)}</p>
                <p className="text-sm text-ink-600 mt-0.5">{v}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 熟练豁免 */}
      {status.saves && Object.keys(status.saves).length > 0 && (
        <div className="mt-4">
          <p className="section-label mb-2">熟练豁免</p>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {keys.map(k => {
              const s = status.saves?.[k];
              if (!s) return null;
              return (
                <div key={k} className="bg-white/70 border border-amber-900/20 rounded-lg p-1.5 text-center">
                  <p className="text-[9px] uppercase tracking-widest text-ink-400">{ATTR_CN[k]}</p>
                  <p className="paper-title text-lg font-bold">
                    {s.value >= 0 ? `+${s.value}` : s.value}
                    {s.proficient && <span className="ml-1 text-[9px] text-amber-700">●</span>}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 熟练技能明细 */}
      {skillProf.length > 0 && (
        <div className="mt-4">
          <p className="section-label mb-2">熟练技能明细</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
            {skillProf.map((s, i) => {
              const a = SKILL_ATTR[s] || 'str';
              const am = Math.floor((Number(attrs[a] ?? 10) - 10) / 2);
              return (
                <div key={i} className="bg-white/70 border border-amber-900/20 rounded px-2 py-1 flex items-center justify-between">
                  <span className="text-[10px] text-ink-600">{s} <span className="text-ink-400">({ATTR_CN[a]})</span></span>
                  <span className="paper-title text-sm font-bold">{am + prof >= 0 ? `+${am + prof}` : am + prof}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
