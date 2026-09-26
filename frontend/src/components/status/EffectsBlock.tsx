/** 力竭 / 状态效果 / 专注（从 StatusPanel 拆出；只做展示，数据由父组件传入）。 */
import type { CharacterStatus } from '../../store/gameStore';

// 5e 力竭：1 级检定劣势 / 2 级速度减半 / 3 级攻防劣势 / 4 级生命上限减半 / 5 级速度为 0 / 6 级死亡
const EXHAUSTION_EFFECTS: Record<number, string> = {
  1: '属性检定具有劣势',
  2: '移动速度减半',
  3: '攻击检定与豁免具有劣势',
  4: '生命值上限减半',
  5: '移动速度降为 0',
  6: '死亡',
};

export default function EffectsBlock({ status, conditions, concentration }: {
  status: CharacterStatus;
  conditions: Array<{
    name: string; description: string; rounds: number;
    damage?: string | number; damageType?: string; heal?: number;
  }>;
  concentration: { spell?: string; level?: number } | null | undefined;
}) {
  return (
    <>
        {/* 力竭：缺粮缺水/长途跋涉累积，长休且吃过口粮时 -1 */}
        {(status.exhaustion ?? 0) > 0 && (
          <div className="rounded-xl bg-orange-50 border border-orange-200 px-2.5 py-2">
            <p className="text-2xs text-orange-700 font-medium">
              力竭 {status.exhaustion} 级
              <span className="text-3xs text-orange-600 font-normal ml-1">
                {EXHAUSTION_EFFECTS[Math.min(6, status.exhaustion ?? 1)] ?? ''}
              </span>
            </p>
          </div>
        )}

        {conditions.length > 0 && (
          <div className="rounded-xl bg-amber-50 border border-amber-200 p-2.5">
            <p className="text-2xs text-amber-700 font-medium mb-1">状态效果</p>
            <div className="space-y-1">
              {conditions.map((c) => (
                <div key={c.name} className="flex items-start gap-1.5">
                  <span className="tag-amber shrink-0">{c.name}</span>
                  <span className="text-3xs text-amber-800 leading-relaxed">
                    {c.description}
                    {c.rounds > 0 ? `（剩余 ${c.rounds} 回合）` : ''}
                    {c.damage ? `（每回合 ${c.damage}${c.damageType ? ` ${c.damageType}` : ''}伤害）` : ''}
                    {c.heal ? `（每回合恢复 ${c.heal}）` : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {concentration?.spell && (
          <div className="rounded-xl bg-brand-50 border border-brand-200 px-2.5 py-2 flex items-center gap-1.5">
            <span className="tag-purple shrink-0">专注</span>
            <span className="text-3xs text-ink-600 truncate">
              {concentration.spell}
              {concentration.level ? `（${concentration.level} 环）` : ''} · 受伤自动掷体质豁免
            </span>
          </div>
        )}
    </>
  );
}
