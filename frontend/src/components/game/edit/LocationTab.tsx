/** 地点标签页：描述行内修改、删除与新增。 */
import type { SendWorld, WorldState } from './types';
import { AddSimpleRow } from './rows';

export default function LocationTab({ world, busy, onSend }: {
  world: WorldState; busy: boolean; onSend: SendWorld;
}) {
  return (
    <div className="space-y-2">
      <AddSimpleRow fields={[['name', '地点名'], ['description', '描述']]} busy={busy}
                    onAdd={(values) => onSend('add_location', values.name, values)} />
      {world.locations.map((loc) => (
        <div key={loc.name} data-location-name={loc.name}
             className="border border-ink-200 rounded-xl p-2 flex items-center gap-2">
          <span className="text-xs text-ink-800 w-32 truncate">{loc.name}</span>
          <input defaultValue={loc.description || ''} placeholder="描述"
                 onBlur={(e) => onSend('update_location', loc.name, { description: e.target.value })}
                 className="flex-1 text-2xs px-2 py-1 rounded-lg border border-ink-200" />
          <button onClick={() => onSend('remove_location', loc.name, {})}
                  className="text-2xs text-red-700 px-2 py-1">删除</button>
        </div>
      ))}
    </div>
  );
}
