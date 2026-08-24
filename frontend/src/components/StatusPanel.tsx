/** 角色状态面板 —— 含装备、持有物、角色身份信息 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

type InvItem = string | { name: string; description?: string; quantity?: number; type?: string; properties?: Record<string, unknown> };
function itemName(it: InvItem): string { return typeof it === 'string' ? it : it.name || '未知物品'; }
function itemDesc(it: InvItem): string {
  if (typeof it === 'object' && it.description) return it.description;
  const name = itemName(it);
  if (/剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(name)) return '武器：近战/远程攻击工具。具体伤害与效果由主持人在叙事中判定。';
  if (/甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(name)) return '防具：提供防护。具体 AC 与效果由主持人在叙事中判定。';
  if (/药水|药剂|瓶|毒|油|圣水/.test(name)) return '消耗品：使用后产生效果，具体由主持人判定。';
  return '杂物：可能用于任务、交易或环境互动，具体用途由主持人判定。';
}


export default function StatusPanel({ onOpenSheet }: { onOpenSheet?: () => void }) {
  const { status, combat } = useGameStore();
  const system = status.game_system || 'dnd5e';
  const [selectedItem, setSelectedItem] = useState<InvItem | null>(null);

  const hpPct = Math.max(0, status.maxHp > 0 ? (status.hp / status.maxHp) * 100 : 0);
  const mpPct = Math.max(0, status.maxMp > 0 ? (status.mp / status.maxMp) * 100 : 0);
  const sanPct = Math.max(0, status.maxSan && status.maxSan > 0 ? ((status.san || 0) / status.maxSan) * 100 : 0);

  // 将背包物品分类
  const inventory = status.inventory || [];
  const weapons = inventory.filter(i =>
    /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(itemName(i))
  );
  const armor = inventory.filter(i =>
    /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(itemName(i))
  );
  const potions = inventory.filter(i =>
    /药水|药剂|瓶|毒|油|圣水/.test(itemName(i))
  );
  const misc = inventory.filter(i =>
    !weapons.includes(i) && !armor.includes(i) && !potions.includes(i)
  );

  return (
    <div className="w-52 bg-white border-r border-gray-200 p-3 flex flex-col gap-2 overflow-y-auto text-[10px]">
      {/* 角色身份 */}
      <div className="text-center pb-2 border-b border-gray-200">
        {status.character_image && <img src={status.character_image} alt="角色" className="w-16 h-16 object-cover rounded-xl border border-gray-200 mx-auto mb-1 shadow-sm" />}
        <h3 className="text-sm font-bold text-gray-900 truncate">
          {status.character_name || '冒险者'}
        </h3>
        <p className="text-[9px] text-gray-500">
          {status.gender && status.gender !== '未指定' ? `${status.gender} · ` : ''}
          {status.race || '?'} {status.char_class || '?'}
        </p>
        <p className="text-[9px] text-gray-400 mt-0.5">
          {system === 'coc' ? `SAN ${status.san || 0} · LUCK ${status.luck || 0}` : `Lv.${status.level} · AC ${status.ac}`}
        </p>
      </div>

      {/* HP + MP */}
      <div className="space-y-1.5">
        <div>
          <div className="flex justify-between text-[9px] mb-0.5">
            <span className="text-gray-500">生命</span>
            <span className={`font-mono font-medium ${hpPct < 30 ? 'text-red-600' : 'text-gray-700'}`}>
              {status.hp}/{status.maxHp}
            </span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{
                background: hpPct < 30
                  ? 'linear-gradient(90deg, #ef4444, #f87171)'
                  : hpPct < 60
                    ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                    : 'linear-gradient(90deg, #22c55e, #4ade80)',
                width: `${hpPct}%`,
              }}
              animate={{ width: `${hpPct}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
        </div>
        {system === 'coc' ? (
          <div>
            <div className="flex justify-between text-[9px] mb-0.5">
              <span className="text-gray-500">理智</span>
              <span className={`font-mono ${sanPct < 30 ? 'text-red-600' : 'text-gray-600'}`}>{status.san}/{status.maxSan}</span>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: sanPct < 30 ? 'linear-gradient(90deg, #7f1d1d, #ef4444)' : 'linear-gradient(90deg, #8b5cf6, #a78bfa)', width: `${sanPct}%` }}
                animate={{ width: `${sanPct}%` }}
                transition={{ duration: 0.4 }}
              />
            </div>
          </div>
        ) : system === 'dnd4e' ? (
          <div>
            <div className="flex justify-between text-[9px] mb-0.5">
              <span className="text-gray-500">回复力</span>
              <span className="font-mono text-gray-600">{status.healing_surges}/{status.max_healing_surges}</span>
            </div>
            <p className="text-[8px] text-gray-400">每次恢复 {status.surge_value || 0} HP</p>
          </div>
        ) : (
          <div>
            <div className="flex justify-between text-[9px] mb-0.5">
              <span className="text-gray-500">魔力</span>
              <span className="font-mono text-gray-600">{status.mp}/{status.maxMp}</span>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: 'linear-gradient(90deg, #6366f1, #818cf8)', width: `${mpPct}%` }}
                animate={{ width: `${mpPct}%` }}
                transition={{ duration: 0.4 }}
              />
            </div>
          </div>
        )}
      </div>

      {/* XP + 金币 */}
      <div className="flex justify-between text-[9px] px-0.5">
        <span className="text-gray-500">经验 <span className="text-gray-700 font-mono">{status.xp}</span></span>
        <span className="text-amber-600 font-medium">金币 {status.gold}</span>
      </div>

      {/* 职业资源 / 法术位摘要 */}
      {((status.class_resources?.length || 0) > 0 || (system === 'dnd5e' && status.spell_slots) || system === 'dnd4e') && (
        <div className="pt-1.5 border-t border-gray-200">
          <p className="section-label mb-1">职业资源</p>
          {(status.class_resources || []).slice(0, 4).map(r => (
            <div key={r.key} className="flex items-center justify-between bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5">
              <span className="text-gray-500 text-[8px] truncate">{r.name}</span>
              <span className="text-gray-700 font-mono font-medium text-[9px]">{r.current}/{r.max}</span>
            </div>
          ))}
          {system === 'dnd5e' && (() => {
            const s = status.spell_slots;
            const arr = Array.isArray(s) ? s : (s && typeof s === 'object' ? (s as { spell_slots?: number[] }).spell_slots : []) || [];
            if (arr.some(n => n > 0)) {
              return <p className="text-[8px] text-gray-400">法术位 {arr.map((n, i) => n > 0 ? `${i + 1}环×${n}` : '').filter(Boolean).join(' ')}</p>;
            }
            return null;
          })()}
          {system === 'dnd4e' && <p className="text-[8px] text-gray-400">行动点 {status.action_points ?? 1}</p>}
        </div>
      )}

      {/* 已习得法术摘要 */}
      {((status.known_spells?.length || 0) > 0) && (
        <div className="pt-1.5 border-t border-gray-200">
          <p className="section-label mb-1">已习得法术（{status.known_spells!.length}）</p>
          <div className="space-y-0.5">
            {status.known_spells!.slice(0, 5).map(s => (
              <div key={s.name} className="text-[8px] text-gray-600 bg-white border border-gray-100 rounded px-1.5 py-0.5 truncate">
                {s.name}：{Number(s.level) === 0 ? '戏法' : `${s.level}环`} {s.school}
              </div>
            ))}
            {(status.known_spells!.length > 5) && <p className="text-[8px] text-gray-400">…还有 {status.known_spells!.length - 5} 个</p>}
          </div>
        </div>
      )}

      {/* 完整角色卡入口 */}
      <button
        onClick={onOpenSheet}
        className="w-full text-center text-[10px] font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 border border-indigo-100 rounded-lg py-1.5 transition-colors"
      >
        查看完整角色卡 →
      </button>

      {/* 装备与物品 */}
      <div className="pt-1.5 border-t border-gray-200 flex-1">
        <p className="section-label mb-1">装备与物品 ({inventory.length})</p>

        {inventory.length === 0 && (
          <p className="text-[9px] text-gray-300 italic">背包空空如也</p>
        )}

        {weapons.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">武器</p>
            {weapons.map((item, i) => (
              <button key={i} onClick={()=>setSelectedItem(item)} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate text-left w-full cursor-pointer hover:bg-indigo-50 hover:border-indigo-200" title="点击查看详情">{itemName(item)}</button>
            ))}
          </div>
        )}

        {armor.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">防具</p>
            {armor.map((item, i) => (
              <button key={i} onClick={()=>setSelectedItem(item)} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate text-left w-full cursor-pointer hover:bg-indigo-50 hover:border-indigo-200" title="点击查看详情">{itemName(item)}</button>
            ))}
          </div>
        )}

        {potions.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">药水</p>
            {potions.map((item, i) => (
              <button key={i} onClick={()=>setSelectedItem(item)} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate text-left w-full cursor-pointer hover:bg-indigo-50 hover:border-indigo-200" title="点击查看详情">{itemName(item)}</button>
            ))}
          </div>
        )}

        {misc.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">杂物</p>
            {misc.slice(0, 6).map((item, i) => (
              <button key={i} onClick={()=>setSelectedItem(item)} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate text-left w-full cursor-pointer hover:bg-indigo-50 hover:border-indigo-200" title="点击查看详情">{itemName(item)}</button>
            ))}
            {misc.length > 6 && <p className="text-[8px] text-gray-400">...还有{misc.length - 6}件</p>}
          </div>
        )}
      </div>

      {/* 战斗状态 */}
      {combat?.active && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-red-50 border border-red-200 rounded-lg p-1.5"
        >
          <p className="text-[9px] text-red-600 font-bold">战斗中</p>
          <p className="text-[9px] text-red-700 truncate">{combat.enemyName}</p>
          <p className="text-[8px] text-gray-500">敌方HP: {combat.enemyHp}</p>
        </motion.div>
      )}

      {/* 物品详情弹窗 */}
      {selectedItem && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={()=>setSelectedItem(null)}>
          <div className="bg-white rounded-xl max-w-sm w-full p-4 shadow-xl" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-gray-900">{itemName(selectedItem)}</h3>
              <button onClick={()=>setSelectedItem(null)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>
            {typeof selectedItem === 'object' && selectedItem.quantity ? <p className="text-[10px] text-gray-400 mb-1">数量：{selectedItem.quantity}</p> : null}
            {typeof selectedItem === 'object' && selectedItem.type ? <p className="text-[10px] text-gray-400 mb-1">类型：{selectedItem.type}</p> : null}
            <p className="text-xs text-gray-600 leading-relaxed">{itemDesc(selectedItem)}</p>
          </div>
        </div>
      )}
    </div>
  );
}
