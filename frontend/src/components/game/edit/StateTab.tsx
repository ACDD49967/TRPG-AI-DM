/** 角色状态标签页：HP/力竭调整、状态效果、伤害抗性/免疫/易伤、属性总览。 */
import { ABILITIES, ABILITY_CN, type CharacterState, type SendState } from './types';
import { DeltaRow, TextAdder } from './rows';

export default function StateTab({ character, busy, onSend }: {
  character: CharacterState | null; busy: boolean; onSend: SendState;
}) {
  const info = character?.character_info || {};
  const resistances: string[] = info.damage_resistances || [];
  const conditions = character?.conditions || [];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-2xs">
        <div className="rounded-lg border border-ink-200 p-2">
          <p className="text-ink-500">HP</p>
          <p className="font-mono text-ink-800">{info.hp ?? 0}/{info.max_hp ?? 0}</p>
        </div>
        <div className="rounded-lg border border-ink-200 p-2">
          <p className="text-ink-500">临时生命</p>
          <p className="font-mono text-ink-800">{info.temporary_hp ?? 0}</p>
        </div>
        <div className="rounded-lg border border-ink-200 p-2">
          <p className="text-ink-500">力竭</p>
          <p className="font-mono text-ink-800">{info.exhaustion ?? 0}</p>
        </div>
        <div className="rounded-lg border border-ink-200 p-2">
          <p className="text-ink-500">金币</p>
          <p className="font-mono text-ink-800">{info.gold ?? 0}</p>
        </div>
      </div>

      <DeltaRow label="调整 HP" onApply={(value) => onSend({ hp: value })} busy={busy} />
      <DeltaRow label="设置力竭（0-6）" onApply={(value) => onSend({ exhaustion: value })} busy={busy} />

      <div>
        <p className="text-2xs text-ink-500 mb-1">状态效果</p>
        <div className="flex flex-wrap gap-1 mb-1">
          {conditions.map((c) => {
            const name = typeof c === 'string' ? c : (c.name || '');
            return (
              <button key={name} onClick={() => onSend({ conditions_remove: [name] })}
                      className="text-2xs px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800"
                      title="点击移除">
                {name} ✕
              </button>
            );
          })}
          {conditions.length === 0 && <span className="text-2xs text-ink-400">无</span>}
        </div>
        <TextAdder placeholder="添加状态（如 中毒）" button="添加"
                   onAdd={(value) => onSend({ conditions_add: [value] })} busy={busy} />
      </div>

      <div>
        <p className="text-2xs text-ink-500 mb-1">伤害抗性 / 免疫 / 易伤</p>
        <div className="flex flex-wrap gap-1 mb-1">
          {resistances.map((r) => (
            <button key={r} onClick={() => onSend({ damage_resistances_remove: [r] })}
                    className="text-2xs px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200 text-slate-700"
                    title="点击移除">
              抗性：{r} ✕
            </button>
          ))}
          {(info.damage_immunities || []).map((r: string) => (
            <button key={`i-${r}`} onClick={() => onSend({ damage_immunities_remove: [r] })}
                    className="text-2xs px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800"
                    title="点击移除">
              免疫：{r} ✕
            </button>
          ))}
          {(info.damage_vulnerabilities || []).map((r: string) => (
            <button key={`v-${r}`} onClick={() => onSend({ damage_vulnerabilities_remove: [r] })}
                    className="text-2xs px-2 py-0.5 rounded-full bg-rose-50 border border-rose-200 text-rose-800"
                    title="点击移除">
              易伤：{r} ✕
            </button>
          ))}
        </div>
        <TextAdder placeholder="伤害类型（如 火焰）" button="加抗性"
                   onAdd={(value) => onSend({ damage_resistances_add: [value] })} busy={busy} />
      </div>

      <div className="text-2xs text-ink-500">
        属性：
        {ABILITIES.map((key) => (
          <span key={key} className="font-mono mr-2">
            {ABILITY_CN[key]} {info.attributes?.[key] ?? 10}
          </span>
        ))}
      </div>
    </div>
  );
}
