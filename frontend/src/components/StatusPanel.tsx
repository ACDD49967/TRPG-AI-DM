/**
 * 角色状态面板 —— 身份 / 生命 / 资源 / 装备 / 战斗
 *
 * 优化点：
 *  - 文字层级从 7~9px 抬升到 11~12px，长名称不再靠放大镜看。
 *  - 装备列表抽成 InvList 组件，四类物品共用一条渲染路径（原先复制了四遍）。
 *  - 物品详情改用统一 Modal：Esc 可关、背景不滚动、装备状态有明确标签。
 *  - 面板宽度自适应：桌面固定 15rem，作为移动端抽屉时占满整屏。
 */

import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { getXpDisplay } from '../gameSystems';
import { InvList, isArmor, isEquipped, isPotion, isWeapon, itemName, type InvItem } from './status/inventory';
import { ItemDetailModal } from './status/ItemDetailModal';
import { MetricsCard } from './status/MetricsCard';
import VitalsBlock from './status/VitalsBlock';
import ResourceBlock from './status/ResourceBlock';
import CombatBlock from './status/CombatBlock';
import TacticalBlock from './status/TacticalBlock';
import EffectsBlock from './status/EffectsBlock';



export default function StatusPanel({ onOpenSheet }: { onOpenSheet?: () => void }) {
  const { status, combat, sessionId, metrics } = useGameStore();
  const initiative = useGameStore((s) => s.initiative);
  const placements = useGameStore((s) => s.placements);

  const system = status.game_system || 'dnd5e';
  const [selectedItem, setSelectedItem] = useState<InvItem | null>(null);

  const toggleEquip = async (it: InvItem) => {
    if (!sessionId) return;
    const name = itemName(it);
    const equipped = !isEquipped(it);
    try {
      await fetch(`/api/game/${sessionId}/equip?username=${encodeURIComponent(status.username || 'default')}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, equipped }),
      });
    } catch {
      // SSE 会推送最新状态；失败时忽略，避免打断操作
    }
  };

  const hpPct = Math.max(0, status.maxHp > 0 ? (status.hp / status.maxHp) * 100 : 0);
  const sanPct = Math.max(0, status.maxSan && status.maxSan > 0 ? ((status.san || 0) / status.maxSan) * 100 : 0);
  const hpTone = hpPct < 30 ? 'from-red-500 to-red-400' : hpPct < 60 ? 'from-amber-500 to-amber-400' : 'from-emerald-500 to-emerald-400';

  const inventory = status.inventory || [];
  const weapons = inventory.filter(isWeapon);
  const armor = inventory.filter(isArmor);
  const potions = inventory.filter(isPotion);
  const misc = inventory.filter((i) => !isWeapon(i) && !isArmor(i) && !isPotion(i));
  const conditions = (status.conditions || []).map((c) =>
    typeof c === 'string'
      ? { name: c, description: '', rounds: 0, damage: '', damageType: '', heal: 0 }
      : {
          name: c.name, description: c.description || '', rounds: c.remaining_rounds || 0,
          damage: c.damage_per_turn || '', damageType: c.damage_type || '', heal: c.heal_per_turn || 0,
        },
  );
  const concentration = status.concentration;

  const spellSlots = (() => {
    if (system !== 'dnd5e') return [];
    const s = status.spell_slots;
    const arr = Array.isArray(s) ? s : s && typeof s === 'object' ? (s as { spell_slots?: number[] }).spell_slots : [];
    return (arr || []).map((n, i) => (n > 0 ? `${i + 1}环×${n}` : '')).filter(Boolean);
  })();

  return (
    <aside className="w-full md:w-60 flex-shrink-0 bg-white md:border-r border-ink-200 flex flex-col overflow-hidden">
      {/* flex flex-col 是给底部用量卡片的 `!mt-auto` 用的：块级容器里 auto 外边距恒为 0，
          侧栏在 1440px 高下会空出下半屏。列向 flex 下子元素仍然是整宽拉伸，视觉不变。 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5 text-xs flex flex-col">
        {/* 角色身份 */}
        <div className="text-center pb-2.5 border-b border-ink-100">
          {status.character_image ? (
            <img
              src={status.character_image}
              alt={status.character_name || '角色'}
              className="w-16 h-16 object-cover rounded-2xl border border-ink-200 mx-auto mb-2 shadow-sm"
            />
          ) : (
            <div className="w-16 h-16 rounded-2xl bg-ink-100 border border-ink-200 mx-auto mb-2 flex items-center justify-center text-2xs text-ink-400">
              无头像
            </div>
          )}
          <h3 className="text-sm font-bold text-ink-900 truncate">{status.character_name || '冒险者'}</h3>
          <p className="text-2xs text-ink-500 mt-0.5">
            {status.gender && status.gender !== '未指定' ? `${status.gender} · ` : ''}
            {status.race || '?'} {status.char_class || '?'}
          </p>
          <p className="text-2xs text-ink-400 mt-0.5 font-mono">
            {system === 'coc' ? `SAN ${status.san || 0} · LUCK ${status.luck || 0}` : `Lv.${status.level} · AC ${status.ac}`}
          </p>
        </div>

        <VitalsBlock system={system} status={status} hpPct={hpPct} hpTone={hpTone} sanPct={sanPct} />

        {/* 经验 / 金币 */}
        <div className="flex justify-between items-center text-2xs px-0.5">
          <span className="text-ink-500">
            经验 <span className="text-ink-700 font-mono font-semibold">{getXpDisplay(system, status.xp, status.level)}</span>
          </span>
          <span className="text-amber-700 font-semibold flex items-center gap-1">
            <span aria-hidden>🪙</span>
            {status.gold}
          </span>
        </div>

        <ResourceBlock system={system} status={status} spellSlots={spellSlots} />

        <button
          onClick={onOpenSheet}
          className="w-full text-center text-2xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100
                     border border-brand-200 rounded-xl py-2 min-h-[40px] transition-colors"
        >
          查看完整角色卡 →
        </button>

        {/* 装备与物品 */}
        <div className="pt-2 border-t border-ink-100">
          <p className="section-label mb-1.5">装备与物品（{inventory.length}）</p>
          {inventory.length === 0 && <p className="text-2xs text-ink-400 italic">背包空空如也</p>}
          <InvList title="武器" items={weapons} onPick={setSelectedItem} />
          <InvList title="防具" items={armor} onPick={setSelectedItem} />
          <InvList title="药水" items={potions} onPick={setSelectedItem} />
          <InvList title="杂物" items={misc} onPick={setSelectedItem} limit={6} />
        </div>

        {/* 战斗状态 */}
        <CombatBlock combat={combat} />

        {/* AI 用量统计：本回合耗时、模型调用次数与 token 消耗 */}
        {/* 先攻顺序：顺序与回合余额由后端维护，前端只展示 */}
        <TacticalBlock placements={placements} initiative={initiative} />

        <EffectsBlock status={status} conditions={conditions} concentration={concentration} />

        {/* 用量卡片贴住侧栏底部：1440px 高度下侧栏内容只占上半屏，底部整块留白显得没做完。
            `!mt-auto` 是为了压过父级 space-y-2.5 给的 margin-top（内容过长时自动退化为普通间距）。 */}
        <div className="!mt-auto pt-1">
          <MetricsCard metrics={metrics} />
        </div>
      </div>

      <ItemDetailModal item={selectedItem} onClose={() => setSelectedItem(null)}
                       onToggleEquip={toggleEquip} />
    </aside>
  );
}
