/** 角色卡正文：按系统选择 D&D 5e/4e、CoC 或通用角色卡。 */
import SpellCard from '../SpellCard';
import DndCharacterSheet from '../DndCharacterSheet';
import CocInvestigatorSheet from '../CocInvestigatorSheet';
import { getXpDisplay } from '../../gameSystems';
import { textValue } from '../../utils/textValue';
import { ATTR_CN } from './monsterFormat';

export default function CharacterSheetBody({
  status, isDndSheet, invName,
}: {
  status: any;
  isDndSheet: boolean;
  invName: (it: any) => string;
}) {
  return (
    <>
      {isDndSheet ? (
        <DndCharacterSheet embedded />
      ) : (status.game_system as string) === 'coc' ? (
        <CocInvestigatorSheet embedded />
      ) : (
        <div className="space-y-4">
          {/* 身份 */}
          <div className="flex items-center gap-3 mb-4">
            {status.character_image ? <img src={status.character_image} alt="角色" className="w-20 h-20 object-cover rounded-xl border border-gray-200" /> : <div className="w-20 h-20 bg-gray-100 rounded-xl flex items-center justify-center text-[9px] text-ink-400">暂无头像</div>}
            <div>
              <p className="text-base font-bold">{status.character_name || '冒险者'}</p>
              <p className="text-[10px] text-ink-500">{status.race || '?'} {status.char_class || '?'} · {status.game_system || 'dnd5e'}</p>
              {status.hit_die && <p className="text-[10px] text-ink-400">生命骰：{status.hit_die}</p>}
            </div>
          </div>

          {/* 核心数值 */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <div className="stat-tile"><p className="text-[9px] text-ink-400">HP</p><p className="text-sm font-bold">{status.hp}/{status.maxHp}</p></div>
            <div className="stat-tile"><p className="text-[9px] text-ink-400">AC</p><p className="text-sm font-bold">{status.ac}</p></div>
            <div className="stat-tile"><p className="text-[9px] text-ink-400">等级</p><p className="text-sm font-bold">{status.level}</p></div>
            <div className="stat-tile"><p className="text-[9px] text-ink-400">经验</p><p className="text-sm font-bold">{getXpDisplay(status.game_system as string, status.xp, status.level)}</p></div>
            {status.game_system === 'coc' && (
              <>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">MP</p><p className="text-sm font-bold">{status.mp}/{status.maxMp}</p></div>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">SAN</p><p className="text-sm font-bold">{status.san}/{status.maxSan}</p></div>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">幸运</p><p className="text-sm font-bold">{status.luck}</p></div>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">伤害加值</p><p className="text-sm font-bold">{status.damage_bonus || '0'}</p></div>
              </>
            )}
            {status.game_system === 'dnd5e' && (
              <>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">熟练加值</p><p className="text-sm font-bold">{status.proficiency_bonus || 2}</p></div>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">金币</p><p className="text-sm font-bold">{status.gold}</p></div>
                <div className="stat-tile"><p className="text-[9px] text-ink-400">法术位</p><p className="text-sm font-bold">{(() => {
                  const ss = status.spell_slots;
                  if (Array.isArray(ss)) return ss.join('/');
                  if (ss && typeof ss === 'object') {
                    const arr = (ss as { spell_slots?: number[] }).spell_slots;
                    const pact = (ss as { pact_slots?: number }).pact_slots;
                    const parts: string[] = [];
                    if (Array.isArray(arr)) parts.push(arr.join('/'));
                    if (pact) parts.push(`契约${pact}`);
                    return parts.join(' · ') || '-';
                  }
                  return '-';
                })()}</p></div>
              </>
            )}
          </div>

          {/* 属性 */}
          <div className="mb-4">
            <p className="section-label mb-1.5">属性</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {Object.entries(status.attributes || {})
                .filter(([k]) => status.game_system === 'coc'
                  ? ['str', 'con', 'dex', 'int', 'pow', 'cha', 'siz', 'edu'].includes(k)
                  : ['str', 'dex', 'con', 'int', 'wis', 'cha'].includes(k))
                .map(([k, v]) => {
                  const m = Math.floor((Number(v) - 10) / 2);
                  return (
                    <div key={k} className="bg-white rounded-lg border border-gray-200 px-2 py-1 flex justify-between">
                      <span className="text-[10px] text-ink-400">{ATTR_CN[k] || k.toUpperCase()}</span>
                      <span className="text-xs font-bold">{textValue(v)}{status.game_system !== 'coc' && <span className={`ml-1 text-[9px] ${m >= 0 ? 'text-emerald-700' : 'text-red-400'}`}>({m >= 0 ? '+' : ''}{m})</span>}</span>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* 技能 / 特长 / 特性 */}
          {((status.skill_proficiencies?.length ?? 0) > 0 || (status.feats?.length ?? 0) > 0 || (status.race_traits?.length ?? 0) > 0 || (status.class_proficiencies?.length ?? 0) > 0) && (
            <div className="space-y-2 mb-4">
              {status.skills && Object.keys(status.skills).length > 0 && (
                <div><p className="section-label mb-1.5">技能数值</p><div className="flex flex-wrap gap-1">{Object.entries(status.skills).map(([k, v]) => <span key={k} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{k}: {textValue(v)}</span>)}</div></div>
              )}
              {status.skill_proficiencies && status.skill_proficiencies.length > 0 && (
                <div><p className="section-label mb-1.5">技能熟练</p><div className="flex flex-wrap gap-1">{status.skill_proficiencies.map((s: any, i: any) => <span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
              )}
              {status.feats && status.feats.length > 0 && (
                <div><p className="section-label mb-1.5">特长</p><div className="space-y-1">{status.feats.map((f: any, i: any) => <div key={i} className="text-[10px] bg-amber-50 text-amber-800 border border-amber-200 rounded px-2 py-1">{f.name}{f.description ? `：${f.description}` : ''}</div>)}</div></div>
              )}
              {status.race_traits && status.race_traits.length > 0 && (
                <div><p className="section-label mb-1.5">种族特性</p><div className="flex flex-wrap gap-1">{status.race_traits.map((s: any, i: any) => <span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
              )}
              {status.class_proficiencies && status.class_proficiencies.length > 0 && (
                <div><p className="section-label mb-1.5">职业熟练</p><div className="flex flex-wrap gap-1">{status.class_proficiencies.map((s: any, i: any) => <span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
              )}
            </div>
          )}

          {/* 已习得法术 */}
          {((status.known_spells?.length ?? 0) > 0) && (
            <div className="space-y-1 mb-4">
              <p className="section-label mb-1.5">已习得法术</p>
              {status.known_spells!.map((s: any) => <SpellCard key={s.name} spell={s} />)}
            </div>
          )}

          {/* 剧本专属 / 额外属性 */}
          {((status.custom_classes?.length ?? 0) > 0 || (status.custom_skills?.length ?? 0) > 0 || (status.extra_attributes && Object.keys(status.extra_attributes).length > 0)) && (
            <div className="space-y-2 mb-4">
              {status.custom_classes && status.custom_classes.length > 0 && (
                <div><p className="section-label mb-1.5">剧本专属职业/身份</p><div className="flex flex-wrap gap-1">{status.custom_classes.map((s: any, i: any) => <span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
              )}
              {status.custom_skills && status.custom_skills.length > 0 && (
                <div><p className="section-label mb-1.5">剧本专属技能</p><div className="flex flex-wrap gap-1">{status.custom_skills.map((s: any, i: any) => <span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
              )}
              {status.extra_attributes && Object.keys(status.extra_attributes).length > 0 && (
                <div><p className="section-label mb-1.5">额外属性</p><div className="flex flex-wrap gap-1">{Object.entries(status.extra_attributes).map(([k, v], i) => <span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{k}: {textValue(v)}</span>)}</div></div>
              )}
            </div>
          )}

          {/* 背景故事 */}
          {status.backstory && (
            <div className="mb-4">
              <p className="section-label mb-1.5">背景故事</p>
              <p className="text-xs text-ink-700 whitespace-pre-wrap leading-relaxed">{status.backstory}</p>
            </div>
          )}

          {/* 背包 */}
          {status.inventory?.length > 0 && (
            <div className="mb-4">
              <p className="section-label mb-1.5">背包</p>
              <div className="flex flex-wrap gap-1">{status.inventory.map((it: any, i: any) => <span key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{invName(it)}</span>)}</div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
