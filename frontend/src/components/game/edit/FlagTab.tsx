/** 剧情旗标标签页：状态下拉、说明行内修改、删除与新增。 */
import type { SendWorld, WorldState } from './types';
import { AddSimpleRow } from './rows';

export default function FlagTab({ world, busy, onSend }: {
  world: WorldState; busy: boolean; onSend: SendWorld;
}) {
  return (
    <div className="space-y-2">
      <AddSimpleRow fields={[['key', '旗标键'], ['status', '状态'], ['description', '说明']]} busy={busy}
                    onAdd={(values) => onSend('set_flag', values.key, values)} />
      {world.plot_flags.map((flag) => (
        <div key={flag.key} data-flag-key={flag.key}
             className="border border-ink-200 rounded-xl p-2 flex items-center gap-2">
          <span className="text-xs text-ink-800 w-40 truncate">{flag.key}</span>
          <select value={flag.status || '进行中'}
                  onChange={(e) => onSend('set_flag', flag.key, { status: e.target.value })}
                  className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
            {['未触发', '进行中', '已解决', '已放弃'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input defaultValue={flag.description || ''} placeholder="说明"
                 onBlur={(e) => onSend('set_flag', flag.key, { description: e.target.value })}
                 className="flex-1 text-2xs px-2 py-1 rounded-lg border border-ink-200" />
          <button onClick={() => onSend('remove_flag', flag.key, {})}
                  className="text-2xs text-red-700 px-2 py-1">删除</button>
        </div>
      ))}
    </div>
  );
}
