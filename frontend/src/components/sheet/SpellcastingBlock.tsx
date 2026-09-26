/** 施法面板：施法属性、攻击加值、豁免 DC、法术位（含契约位）与已习得法术。 */
import type { CharacterStatus } from '../../store/gameTypes';
import SpellCard from '../SpellCard';
import { ATTR_CN } from './helpers';

export default function SpellcastingBlock({ status, spellSlots, castAttr, castMod, prof }: {
  status: CharacterStatus;
  spellSlots: CharacterStatus['spell_slots'];
  castAttr: string;
  castMod: number;
  prof: number;
}) {
  const known = status.known_spells || [];
  if (!spellSlots && known.length === 0) return null;
  return (
    <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
      <p className="section-label mb-2">施法</p>
      {spellSlots && (
      <div className="text-[10px] text-ink-700 space-y-0.5">
        <p>施法属性：{ATTR_CN[castAttr] || castAttr}</p>
        <p>法术攻击加值：d20{castMod + prof >= 0 ? `+${castMod + prof}` : castMod + prof}</p>
        <p>法术豁免 DC：{8 + castMod + prof}（8 + 熟练{prof >= 0 ? `+${prof}` : prof} + {ATTR_CN[castAttr] || castAttr}调整{castMod >= 0 ? `+${castMod}` : castMod}）</p>
        <p>法术位：{
          (() => {
            const arr = Array.isArray(spellSlots)
              ? spellSlots
              : (typeof spellSlots === 'object' && spellSlots ? (spellSlots as { spell_slots?: number[] }).spell_slots : []) || [];
            const rings = arr.map((n, i) => n > 0 ? `${i + 1}环×${n}` : null).filter(Boolean).join(' · ');
            const pact = !Array.isArray(spellSlots) && typeof spellSlots === 'object' && spellSlots && (spellSlots as { pact_slots?: number; pact_slot_level?: number }).pact_slots;
            const pactLevel = !Array.isArray(spellSlots) && typeof spellSlots === 'object' && spellSlots && (spellSlots as { pact_slot_level?: number }).pact_slot_level;
            return (rings || '—') + (pact ? ` · 契约法术位×${pact}（${pactLevel ?? 1}环）` : '');
          })()
          }</p>
      </div>
      )}
      <div className="mt-2 space-y-1">
        <p className="section-label">已习得法术（{known.length}）</p>
        {known.length === 0 && (
          <p className="text-[10px] text-ink-400">暂无。习得新法术后会自动出现在这里，点开可查看完整效果。</p>
        )}
        {known.map(s => <SpellCard key={s.name} spell={s} paper />)}
      </div>
    </div>
  );
}
