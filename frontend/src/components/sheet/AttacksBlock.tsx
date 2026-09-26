/** 攻击面板：按武器名判断用力量还是敏捷，给出 d20 加值与伤害骰。 */
import { invName, weaponDice, type InventoryItem } from './helpers';

export default function AttacksBlock({ weapons, attrs, prof }: {
  weapons: InventoryItem[];
  attrs: Record<string, number>;
  prof: number;
}) {
  if (weapons.length === 0) return null;
  return (
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
              <span className="text-[10px] text-ink-700">{name}</span>
              <span className="text-[10px] text-ink-500 font-mono">
                d20{atkMod >= 0 ? `+${atkMod}` : atkMod} · {weaponDice(name)}+{Math.floor((Number(attrs[attrKey] ?? 10) - 10) / 2)} 伤害
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
