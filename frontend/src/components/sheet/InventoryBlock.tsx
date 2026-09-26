/** 防具 / 物品两栏（物品最多显示 8 条），以及背景故事。 */
import { invName, type InventoryItem } from './helpers';

export default function InventoryBlock({ armor, misc }: {
  armor: InventoryItem[];
  misc: InventoryItem[];
}) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-2">
      <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
        <p className="section-label mb-1">防具</p>
        {armor.length === 0 ? <p className="text-[10px] text-gray-300">—</p> : armor.map((a, i) => <p key={i} className="text-[10px] text-ink-700">{invName(a)}</p>)}
      </div>
      <div className="bg-white/70 border border-amber-900/20 rounded-lg p-3">
        <p className="section-label mb-1">物品</p>
        {misc.length === 0 ? <p className="text-[10px] text-gray-300">—</p> : misc.slice(0, 8).map((m, i) => <p key={i} className="text-[10px] text-ink-700">{invName(m)}</p>)}
      </div>
    </div>
  );
}
