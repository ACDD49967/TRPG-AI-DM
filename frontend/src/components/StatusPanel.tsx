/** 角色状态面板 —— 含装备、持有物、角色身份信息 */

import { motion } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

const ATTR_LABELS: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
  pow: '意志', siz: '体型', edu: '教育',
};
const ATTR_ICONS: Record<string, string> = {
  str: '💪', dex: '🏃', con: '🛡️', int: '📚', wis: '👁️', cha: '👑',
  pow: '🔥', siz: '📏', edu: '🎓',
};

export default function StatusPanel() {
  const { status, combat } = useGameStore();
  const system = status.game_system || 'dnd5e';

  const hpPct = Math.max(0, status.maxHp > 0 ? (status.hp / status.maxHp) * 100 : 0);
  const mpPct = Math.max(0, status.maxMp > 0 ? (status.mp / status.maxMp) * 100 : 0);
  const sanPct = Math.max(0, status.maxSan && status.maxSan > 0 ? ((status.san || 0) / status.maxSan) * 100 : 0);

  // 将背包物品分类
  const inventory = status.inventory || [];
  const weapons = inventory.filter(i =>
    /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(i)
  );
  const armor = inventory.filter(i =>
    /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(i)
  );
  const potions = inventory.filter(i =>
    /药水|药剂|瓶|毒|油|圣水/.test(i)
  );
  const misc = inventory.filter(i =>
    !weapons.includes(i) && !armor.includes(i) && !potions.includes(i)
  );

  return (
    <div className="w-48 bg-gray-50/80 border-r border-gray-200 p-2.5 flex flex-col gap-2 overflow-y-auto text-[10px]">
      {/* 角色身份 */}
      <div className="text-center pb-2 border-b border-gray-200">
        <h3 className="text-xs font-bold text-gray-800 truncate">
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
          <div className="flex justify-between text-[9px] mb-0.5">
            <span className="text-gray-500">回复力</span>
            <span className="font-mono text-gray-600">{status.healing_surges}/{status.max_healing_surges}</span>
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
        <span className="text-amber-600 font-medium">🪙 {status.gold}</span>
      </div>

      {/* 属性 */}
      <div className="pt-1.5 border-t border-gray-200">
        <p className="text-[9px] text-gray-400 mb-1">属性</p>
        <div className="grid grid-cols-2 gap-0.5">
          {Object.entries(ATTR_LABELS).map(([k, label]) => {
            const v = status.attributes[k] || 10;
            const m = Math.floor((v - 10) / 2);
            return (
              <div key={k} className="flex items-center justify-between bg-white rounded px-1.5 py-0.5 border border-gray-100">
                <span className="text-gray-500 text-[8px]">{ATTR_ICONS[k]} {label}</span>
                <span className="text-gray-700 font-mono font-medium text-[9px]">
                  {v}
                  <span className={m >= 0 ? 'text-emerald-500' : 'text-red-400'}>
                    ({m >= 0 ? '+' : ''}{m})
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 装备与物品 */}
      <div className="pt-1.5 border-t border-gray-200 flex-1">
        <p className="text-[9px] text-gray-400 mb-1">装备与物品 ({inventory.length})</p>

        {inventory.length === 0 && (
          <p className="text-[9px] text-gray-300 italic">背包空空如也</p>
        )}

        {weapons.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">⚔ 武器</p>
            {weapons.map((item, i) => (
              <p key={i} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate" title={item}>{item}</p>
            ))}
          </div>
        )}

        {armor.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">🛡 防具</p>
            {armor.map((item, i) => (
              <p key={i} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate" title={item}>{item}</p>
            ))}
          </div>
        )}

        {potions.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">🧪 药水</p>
            {potions.map((item, i) => (
              <p key={i} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate" title={item}>{item}</p>
            ))}
          </div>
        )}

        {misc.length > 0 && (
          <div className="mb-1">
            <p className="text-[8px] text-gray-400 font-medium mb-0.5">📦 杂物</p>
            {misc.slice(0, 6).map((item, i) => (
              <p key={i} className="text-[9px] text-gray-700 bg-white rounded px-1.5 py-0.5 border border-gray-100 mb-0.5 truncate" title={item}>{item}</p>
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
          <p className="text-[9px] text-red-600 font-bold">⚔ 战斗中</p>
          <p className="text-[9px] text-red-700 truncate">{combat.enemyName}</p>
          <p className="text-[8px] text-gray-500">敌方HP: {combat.enemyHp}</p>
        </motion.div>
      )}
    </div>
  );
}
