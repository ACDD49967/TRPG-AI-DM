/** D&D 5e/4e 官方风格纸质角色卡 */

import { useGameStore } from '../store/gameStore';
import type { CharacterStatus } from '../store/gameStore';
import SpellCard from './SpellCard';

const ATTR_CN: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
};

function mod(v: number): string {
  const m = Math.floor((v - 10) / 2);
  return `${m >= 0 ? '+' : ''}${m}`;
}

function invName(it: string | { name: string }): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}

const SKILL_ATTR: Record<string, string> = {
  '运动': 'str', '特技': 'dex', '巧手': 'dex', '潜行': 'dex',
  '奥秘': 'int', '历史': 'int', '调查': 'int', '自然': 'int', '宗教': 'int',
  '洞悉': 'wis', '医药': 'wis', '察觉': 'wis', '生存': 'wis',
  '欺瞒': 'cha', '威吓': 'cha', '表演': 'cha', '游说': 'cha',
};

const WEAPON_DICE: Record<string, string> = {
  '匕首': '1d4', '短剑': '1d6', '长剑': '1d8', '细剑': '1d8',
  '巨剑': '2d6', '手斧': '1d6', '战斧': '1d8', '巨斧': '1d12',
  '短弓': '1d6', '长弓': '1d8', '轻弩': '1d8', '重弩': '1d10',
  '矛': '1d6', '木棍': '1d6', '棍棒': '1d6', '钉头锤': '1d6',
  '长棍': '1d8', '巨锤': '2d6', '戟': '1d10', '鞭': '1d4',
};

const SPELLCAST_MOD: Record<string, string> = {
  '法师': 'int', '牧师': 'wis', '德鲁伊': 'wis', '游侠': 'wis',
  '吟游诗人': 'cha', '术士': 'cha', '邪术师': 'cha', '圣武士': 'cha',
};

function weaponDice(name: string): string {
  for (const [k, v] of Object.entries(WEAPON_DICE)) {
    if (name.includes(k)) return v;
  }
  return '1d8';
}

export default function DndCharacterSheet({ onClose }: { onClose?: () => void }) {
  const { status } = useGameStore();
  const attrs = status.attributes || {};
  const keys = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
  const prof = status.proficiency_bonus ?? 2;
  const speed = status.speed ?? '30尺';
  const inventory = status.inventory || [];
  const weapons = inventory.filter(i => /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(invName(i)));
  const armor = inventory.filter(i => /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(invName(i)));
  const misc = inventory.filter(i => !weapons.includes(i) && !armor.includes(i));
  const skillProf = status.skill_proficiencies || [];
  const castAttr = SPELLCAST_MOD[status.char_class || ''] || 'int';
  const castMod = Math.floor((Number(attrs[castAttr] ?? 10) - 10) / 2);
  const spellSlots = status.spell_slots;

  return (
    <div className="paper-card rounded-xl max-w-3xl w-full max-h-[88vh] overflow-y-auto p-5 text-gray-900">
      {/* 顶部信息 */}
      <div className="flex items-start justify-between border-b-2 border-amber-900/30 pb-3">
        <div>
          <h3 className="paper-title text-2xl font-black tracking-wide">{status.character_name || '冒险者'}</h3>
          <p className="text-xs text-gray-600 mt-1">
            {status.race || '?'} · {status.char_class || '?'} · Lv.{status.level} · {status.game_system === 'dnd4e' ? 'D&D 4e' : 'D&D 5e'}
          </p>
        </div>
        <div className="flex items-start gap-3">
          <div className="text-right">
            <div className="paper-title text-4xl font-black text-amber-900/80">{status.ac ?? 10}</div>
            <p className="text-[10px] uppercase tracking-widest text-gray-500">护甲等级</p>
          </div>
          {onClose && <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>}
        </div>
      </div>

      {/* 核心数值 */}
      <div className="grid grid-cols-4 gap-2 mt-3">
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">生命值</p>
          <p className="paper-title text-xl font-bold">{status.hp}/{status.maxHp}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">先攻</p>
          <p className="paper-title text-xl font-bold">{mod(Number(attrs.dex ?? 10))}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">速度</p>
          <p className="paper-title text-xl font-bold">{speed}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">熟练加值</p>
          <p className="paper-title text-xl font-bold">+{prof}</p>
        </div>
      </div>

      {/* 被动感知 */}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">被动感知</p>
          <p className="paper-title text-lg font-bold">{status.passive_perception ?? (10 + mod(Number(attrs.wis ?? 10)).replace('+',''))}</p>
        </div>
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-gray-500">生命骰</p>
          <p className="paper-title text-lg font-bold">{status.hit_die || '1d8'}</p>
        </div>
      </div>

      {/* 职业资源 */}
      {((status.class_resources?.length || 0) > 0 || status.game_system === 'dnd4e') && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          {(status.class_resources || []).map((r, i) => (
            <details key={r.key || i} className="group bg-white/70 border border-amber-900/20 rounded-lg p-2">
              <summary className="cursor-pointer flex items-baseline justify-between">
                <p className="text-[10px] uppercase tracking-widest text-gray-500">{r.name}<span className="ml-1 group-open:hidden">▸</span></p>
                <p className="paper-title text-lg font-bold">{r.current}/{r.max}</p>
              </summary>
              {r.desc ? <p className="text-[9px] text-gray-500 mt-1 pt-1 border-t border-amber-900/10">{r.desc}</p> : null}
            </details>
          ))}
          {status.game_system === 'dnd4e' && (
            <>
              <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2">
                <div className="flex items-baseline justify-between">
                  <p className="text-[10px] uppercase tracking-widest text-gray-500">行动点</p>
                  <p className="paper-title text-lg font-bold">{status.action_points ?? 1}</p>
                </div>
                <p className="text-[9px] text-gray-500 mt-0.5">长休重置为 1，里程碑 +1</p>
              </div>
              <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2">
                <div className="flex items-baseline justify-between">
                  <p className="text-[10px] uppercase tracking-widest text-gray-500">回复力</p>
                  <p className="paper-title text-lg font-bold">{status.healing_surges ?? 0}/{status.max_healing_surges ?? 0}</p>
                </div>
                <p className="text-[9px] text-gray-500 mt-0.5">每次回复 {status.surge_value ?? 0} HP</p>
              </div>
            </>
          )}
        </div>
      )}

      {/* 六维属性 */}
      <div className="mt-4">
        <p className="section-label mb-2">属性</p>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {keys.map(k => {
            const v = Number(attrs[k] ?? 10);
            return (
              <div key={k} className="bg-white border-2 border-amber-900/30 rounded-lg py-2 text-center shadow-sm">
                <p className="text-[9px] uppercase tracking-widest text-gray-400">{ATTR_CN[k]}</p>
                <p className="paper-title text-2xl font-black">{mod(v)}</p>
                <p className="text-sm text-gray-600 mt-0.5">{v}</p>
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
                  <p className="text-[9px] uppercase tracking-widest text-gray-400">{ATTR_CN[k]}</p>
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
                  <span className="text-[10px] text-gray-600">{s} <span className="text-gray-400">({ATTR_CN[a]})</span></span>
                  <span className="paper-title text-sm font-bold">{am + prof >= 0 ? `+${am + prof}` : am + prof}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 特性 / 特长 */}
      {(status.race_traits?.length || status.feats?.length || status.class_proficiencies?.length) ? (
        <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">特性 / 特长 / 背景特征</p>
          <div className="space-y-1">
            {(status.race_traits || []).map((t, i) => <p key={i} className="text-[10px] text-gray-600">· {t}</p>)}
            {(status.class_proficiencies || []).map((t, i) => <p key={i} className="text-[10px] text-gray-600">· {t}</p>)}
            {(status.feats || []).map((f, i) => <p key={i} className="text-[10px] text-amber-800">· {f.name}</p>)}
          </div>
        </div>
      ) : null}

      {/* 攻击 */}
      {weapons.length > 0 && (
        <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-2">攻击</p>
          <div className="space-y-1">
            {weapons.map((w, i) => {
              const name = invName(w);
              const useDex = /弓|弩|匕首|细剑|短剑/.test(name);
              const attrKey = useDex ? 'dex' : 'str';
              const atkMod = Math.floor((Number(attrs[attrKey] ?? 10) - 10) / 2) + prof;
              return (
                <div key={i} className="flex items-center justify-between border-b border-gray-100 py-0.5 last:border-0">
                  <span className="text-[10px] text-gray-700">{name}</span>
                  <span className="text-[10px] text-gray-500 font-mono">
                    d20{atkMod >= 0 ? `+${atkMod}` : atkMod} · {weaponDice(name)}+{Math.floor((Number(attrs[attrKey] ?? 10) - 10) / 2)} 伤害
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 施法 */}
      {spellSlots && (
        <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-2">施法</p>
          <div className="text-[10px] text-gray-700 space-y-0.5">
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
          <div className="mt-2 space-y-1">
            <p className="section-label">已习得法术（{(status.known_spells || []).length}）</p>
            {(status.known_spells || []).length === 0 && (
              <p className="text-[10px] text-gray-400">暂无。习得新法术后会自动出现在这里，点开可查看完整效果。</p>
            )}
            {(status.known_spells || []).map(s => <SpellCard key={s.name} spell={s} paper />)}
          </div>
        </div>
      )}

      {/* 防具 / 物品 */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">防具</p>
          {armor.length === 0 ? <p className="text-[10px] text-gray-300">—</p> : armor.map((a, i) => <p key={i} className="text-[10px] text-gray-700">{invName(a)}</p>)}
        </div>
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">物品</p>
          {misc.length === 0 ? <p className="text-[10px] text-gray-300">—</p> : misc.slice(0, 8).map((m, i) => <p key={i} className="text-[10px] text-gray-700">{invName(m)}</p>)}
        </div>
      </div>

      {/* 背景 */}
      {status.backstory ? (
        <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">背景故事</p>
          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{status.backstory}</p>
        </div>
      ) : null}
    </div>
  );
}
