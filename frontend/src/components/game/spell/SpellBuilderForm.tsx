/** 自建法术/仪式表单：受控字段由父组件持有。 */
export default function SpellBuilderForm({
  dmSpell, setDmSpell, onSave,
}: {
  [key: string]: any;
}) {
  return (
    <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
      <p className="text-xs font-bold text-ink-700">自建法术 / 仪式</p>
      <div className="grid grid-cols-2 gap-2">
        <input value={dmSpell.name} onChange={(e: any) => setDmSpell({ ...dmSpell, name: e.target.value })} placeholder="法术名称 *" className="input-field text-xs" />
        <input value={dmSpell.level} onChange={(e: any) => setDmSpell({ ...dmSpell, level: e.target.value })} placeholder="环位（0=戏法）" className="input-field text-xs" />
        <input value={dmSpell.school} onChange={(e: any) => setDmSpell({ ...dmSpell, school: e.target.value })} placeholder="学派（塑能/防护/...）" className="input-field text-xs" />
        <input value={dmSpell.casting_time} onChange={(e: any) => setDmSpell({ ...dmSpell, casting_time: e.target.value })} placeholder="施法时间（1 动作）" className="input-field text-xs" />
        <input value={dmSpell.range} onChange={(e: any) => setDmSpell({ ...dmSpell, range: e.target.value })} placeholder="施法距离（150 尺/触及/自身）" className="input-field text-xs" />
        <input value={dmSpell.components} onChange={(e: any) => setDmSpell({ ...dmSpell, components: e.target.value })} placeholder="成分（V、S、M）" className="input-field text-xs" />
        <input value={dmSpell.duration} onChange={(e: any) => setDmSpell({ ...dmSpell, duration: e.target.value })} placeholder="持续时间（立即/专注）" className="input-field text-xs" />
        <input value={dmSpell.classes} onChange={(e: any) => setDmSpell({ ...dmSpell, classes: e.target.value })} placeholder="职业（术士、法师）" className="input-field text-xs" />
      </div>
      <label className="flex items-center gap-2 text-[10px] text-ink-500">
        <input type="checkbox" checked={dmSpell.ritual} onChange={(e: any) => setDmSpell({ ...dmSpell, ritual: e.target.checked })} /> 仪式法术
      </label>
      <textarea value={dmSpell.description} onChange={(e: any) => setDmSpell({ ...dmSpell, description: e.target.value })} placeholder="效果描述（含伤害、豁免、升环效应）" rows={3} className="input-field text-xs resize-none w-full" />
      <button onClick={onSave} className="btn-xs-paper mt-1">保存到当前剧本法术库</button>
    </div>
  );
}
