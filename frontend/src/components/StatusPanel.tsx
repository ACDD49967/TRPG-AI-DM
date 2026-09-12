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
import { motion } from 'framer-motion';
import { useGameStore } from '../store/gameStore';
import { getXpDisplay } from '../gameSystems';
import Modal from './ui/Modal';

type InvItem = string | { name: string; description?: string; quantity?: number; type?: string; properties?: Record<string, unknown>; equipped?: boolean };

function itemName(it: InvItem): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}
function itemLabel(it: InvItem): string {
  const q = typeof it === 'object' && it.quantity && it.quantity > 1 ? ` ×${it.quantity}` : '';
  return `${itemName(it)}${q}`;
}
function itemDesc(it: InvItem): string {
  if (typeof it === 'object' && it.description) return it.description;
  const name = itemName(it);
  if (/剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(name)) return '武器：近战/远程攻击工具。具体伤害与效果由主持人在叙事中判定。';
  if (/甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(name)) return '防具：提供防护。具体 AC 与效果由主持人在叙事中判定。';
  if (/药水|药剂|瓶|毒|油|圣水/.test(name)) return '消耗品：使用后产生效果，具体由主持人判定。';
  return '杂物：可能用于任务、交易或环境互动，具体用途由主持人判定。';
}
function isEquipped(it: InvItem): boolean {
  return typeof it === 'object' && it.equipped === true;
}
const isWeapon = (it: InvItem) => /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(itemName(it));
const isArmor = (it: InvItem) => /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(itemName(it));
const isPotion = (it: InvItem) => /药水|药剂|瓶|毒|油|圣水/.test(itemName(it));

/** 分组物品列表：四类物品共用一条渲染路径 */
function InvList({
  title,
  items,
  onPick,
  limit,
}: {
  title: string;
  items: InvItem[];
  onPick: (it: InvItem) => void;
  limit?: number;
}) {
  if (items.length === 0) return null;
  const shown = limit ? items.slice(0, limit) : items;
  return (
    <div className="mb-2 last:mb-0">
      <p className="text-3xs text-ink-400 font-medium mb-1 flex items-center gap-1">
        {title}
        <span className="text-ink-500 font-mono">{items.length}</span>
      </p>
      <div className="space-y-0.5">
        {shown.map((item, i) => (
          <button
            key={i}
            onClick={() => onPick(item)}
            title="点击查看详情"
            className="w-full text-left text-2xs text-ink-700 bg-white rounded-lg px-2 py-1 border border-ink-200
                       hover:bg-brand-50 hover:border-brand-300 transition-colors duration-150 flex items-center gap-1.5"
          >
            <span className="truncate flex-1">{itemLabel(item)}</span>
            {isEquipped(item) && (
              <span className="shrink-0 text-3xs px-1 rounded border border-brand-200 bg-brand-50 text-brand-600">已装备</span>
            )}
          </button>
        ))}
      </div>
      {limit && items.length > limit && <p className="text-3xs text-ink-400 mt-1">…还有 {items.length - limit} 件</p>}
    </div>
  );
}

export default function StatusPanel({ onOpenSheet }: { onOpenSheet?: () => void }) {
  const { status, combat, sessionId } = useGameStore();
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

  const spellSlots = (() => {
    if (system !== 'dnd5e') return [];
    const s = status.spell_slots;
    const arr = Array.isArray(s) ? s : s && typeof s === 'object' ? (s as { spell_slots?: number[] }).spell_slots : [];
    return (arr || []).map((n, i) => (n > 0 ? `${i + 1}环×${n}` : '')).filter(Boolean);
  })();

  return (
    <aside className="w-full md:w-60 flex-shrink-0 bg-white md:border-r border-ink-200 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5 text-xs">
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

        {/* 生命 / 理智 / 回复力 */}
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-2xs mb-1">
              <span className="text-ink-500">生命</span>
              <span className={`font-mono font-semibold ${hpPct < 30 ? 'text-red-600' : 'text-ink-700'}`}>
                {status.hp}/{status.maxHp}
              </span>
            </div>
            <div className="h-2 bg-ink-200/70 rounded-full overflow-hidden">
              <motion.div
                className={`h-full rounded-full bg-gradient-to-r ${hpTone}`}
                initial={false}
                animate={{ width: `${hpPct}%` }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
          </div>

          {system === 'coc' && (
            <div>
              <div className="flex justify-between text-2xs mb-1">
                <span className="text-ink-500">理智</span>
                <span className={`font-mono ${sanPct < 30 ? 'text-red-600' : 'text-ink-600'}`}>
                  {status.san}/{status.maxSan}
                </span>
              </div>
              <div className="h-2 bg-ink-200/70 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full ${sanPct < 30 ? 'bg-gradient-to-r from-red-800 to-red-500' : 'bg-gradient-to-r from-violet-500 to-violet-400'}`}
                  initial={false}
                  animate={{ width: `${sanPct}%` }}
                  transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            </div>
          )}

          {system === 'dnd4e' && (
            <div className="rounded-xl bg-ink-50 border border-ink-200 px-2.5 py-1.5">
              <div className="flex justify-between text-2xs">
                <span className="text-ink-500">回复力</span>
                <span className="font-mono text-ink-700 font-semibold">
                  {status.healing_surges}/{status.max_healing_surges}
                </span>
              </div>
              <p className="text-3xs text-ink-400 mt-0.5">每次恢复 {status.surge_value || 0} HP</p>
            </div>
          )}
        </div>

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

        <button
          onClick={onOpenSheet}
          className="w-full text-center text-2xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100
                     border border-brand-200 rounded-xl py-2 transition-colors"
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
        {combat?.active && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl bg-red-50 border border-red-200 p-2.5"
          >
            <p className="text-2xs text-red-600 font-bold flex items-center gap-1.5 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse-soft" aria-hidden />
              战斗中
            </p>
            <div className="space-y-1">
              {(combat.enemies && combat.enemies.length > 0
                ? combat.enemies
                : [{ name: combat.enemyName, hp: combat.enemyHp }]
              ).map((e) => (
                <div key={e.name} className="flex items-center justify-between gap-2">
                  <span className="text-2xs text-red-700 truncate">{e.name}</span>
                  <span className="text-2xs text-ink-500 font-mono shrink-0">HP {e.hp}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>

      {/* 物品详情弹窗 */}
      <Modal
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
        size="sm"
        icon="🎒"
        title={selectedItem ? itemName(selectedItem) : ''}
        footer={
          <>
            <button onClick={() => setSelectedItem(null)} className="btn-secondary text-xs px-3 py-1.5">
              关闭
            </button>
            <button
              onClick={() => selectedItem && toggleEquip(selectedItem)}
              className={selectedItem && isEquipped(selectedItem) ? 'btn-secondary text-xs px-3 py-1.5' : 'btn-primary text-xs px-3 py-1.5'}
            >
              {selectedItem && isEquipped(selectedItem) ? '卸下装备' : '装备此物品'}
            </button>
          </>
        }
      >
        {selectedItem && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {isEquipped(selectedItem) && <span className="tag-purple">已装备</span>}
              {typeof selectedItem === 'object' && selectedItem.type && <span className="tag-gray">{selectedItem.type}</span>}
              {typeof selectedItem === 'object' && selectedItem.quantity ? (
                <span className="tag-gray">数量 {selectedItem.quantity}</span>
              ) : null}
            </div>
            <p className="text-sm text-ink-600 leading-relaxed">{itemDesc(selectedItem)}</p>
          </div>
        )}
      </Modal>
    </aside>
  );
}
