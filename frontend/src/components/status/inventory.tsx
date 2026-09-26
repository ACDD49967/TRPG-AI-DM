/**
 * 背包物品的工具函数与分组列表。
 *
 * 从 StatusPanel 拆出：物品名/描述/装备态的判断与分类（武器/护甲/药水）被面板与
 * 物品详情弹窗共用，单独成文件后两边都不必再各自实现一遍。
 */

export type InvItem = string | { name: string; description?: string; quantity?: number; type?: string; properties?: Record<string, unknown>; equipped?: boolean };

export function itemName(it: InvItem): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}

export function itemLabel(it: InvItem): string {
  const q = typeof it === 'object' && it.quantity && it.quantity > 1 ? ` ×${it.quantity}` : '';
  return `${itemName(it)}${q}`;
}
export function itemDesc(it: InvItem): string {
  if (typeof it === 'object' && it.description) return it.description;
  const name = itemName(it);
  if (/剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(name)) return '武器：近战/远程攻击工具。具体伤害与效果由主持人在叙事中判定。';
  if (/甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(name)) return '防具：提供防护。具体 AC 与效果由主持人在叙事中判定。';
  if (/药水|药剂|瓶|毒|油|圣水/.test(name)) return '消耗品：使用后产生效果，具体由主持人判定。';
  return '杂物：可能用于任务、交易或环境互动，具体用途由主持人判定。';
}
export function isEquipped(it: InvItem): boolean {
  return typeof it === 'object' && it.equipped === true;
}
export const isWeapon = (it: InvItem) => /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(itemName(it));
export const isArmor = (it: InvItem) => /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(itemName(it));
export const isPotion = (it: InvItem) => /药水|药剂|瓶|毒|油|圣水/.test(itemName(it));

/** 分组物品列表：四类物品共用一条渲染路径 */
export function InvList({
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
