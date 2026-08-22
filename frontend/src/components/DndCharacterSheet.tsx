/** D&D 5e/4e 官方风格纸质角色卡 */

import { useGameStore } from '../store/gameStore';
import type { CharacterStatus } from '../store/gameStore';

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

      {/* 技能 / 特性 */}
      {(status.skill_proficiencies?.length || status.skills || status.feats?.length) ? (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
            <p className="section-label mb-1">技能熟练</p>
            {status.skills && Object.keys(status.skills).length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {Object.entries(status.skills).map(([k, v]) => <span key={k} className="text-[10px] bg-indigo-50 border border-indigo-200 rounded px-2 py-0.5">{k}: {v}</span>)}
              </div>
            ) : (
              <div className="flex flex-wrap gap-1">
                {(status.skill_proficiencies || []).map((s, i) => <span key={i} className="text-[10px] bg-indigo-50 border border-indigo-200 rounded px-2 py-0.5">{s}</span>)}
              </div>
            )}
          </div>
          <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
            <p className="section-label mb-1">特性 / 特长</p>
            <div className="space-y-1">
              {(status.race_traits || []).map((t, i) => <p key={i} className="text-[10px] text-gray-600">· {t}</p>)}
              {(status.feats || []).map((f, i) => <p key={i} className="text-[10px] text-amber-800">· {f.name}</p>)}
              {(status.class_proficiencies || []).map((t, i) => <p key={i} className="text-[10px] text-gray-600">· {t}</p>)}
            </div>
          </div>
        </div>
      ) : null}

      {/* 武器 / 防具 / 物品 */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">武器</p>
          {weapons.length === 0 ? <p className="text-[10px] text-gray-300">—</p> : weapons.map((w, i) => (
            <p key={i} className="text-[10px] text-gray-700 border-b border-gray-100 py-0.5 last:border-0">{invName(w)} <span className="text-gray-400">d20+{prof}+{mod(Number(attrs.dex ?? 10))}</span></p>
          ))}
        </div>
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
