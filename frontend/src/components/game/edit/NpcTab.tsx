/** NPC 标签页：态度 / 所在地点 / HP 的行内修改与删除。 */
import { ATTITUDES, type SendWorld, type WorldState } from './types';
import { AddNpcRow } from './rows';

export default function NpcTab({ world, busy, onSend }: {
  world: WorldState; busy: boolean; onSend: SendWorld;
}) {
  return (
    <div className="space-y-2">
      <AddNpcRow busy={busy} onAdd={(changes) => onSend('add_npc', String(changes.name), changes)} />
      {world.npcs.map((npc) => (
        <div key={npc.name} className="border border-ink-200 rounded-xl p-2 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-ink-800">{npc.name}</span>
            <span className="text-3xs text-ink-400">{npc.role || ''}</span>
            <span className="flex-1" />
            <span className="text-3xs font-mono text-ink-500">
              HP {npc.hp ?? 0}/{npc.max_hp ?? 0} · AC {npc.ac ?? 0} · Lv{npc.level ?? 1}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <select value={npc.attitude || '中立'}
                    onChange={(e) => onSend('update_npc', npc.name, { attitude: e.target.value })}
                    className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
              {ATTITUDES.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <input defaultValue={npc.location || ''} placeholder="所在地点"
                   onBlur={(e) => onSend('update_npc', npc.name, { location: e.target.value })}
                   className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-32" />
            <input type="number" defaultValue={npc.hp ?? 0}
                   onBlur={(e) => onSend('update_npc', npc.name,
                     { hp: Number(e.target.value), alive: Number(e.target.value) > 0 })}
                   className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-20" />
            <button onClick={() => onSend('remove_npc', npc.name, {})}
                    className="text-2xs text-red-700 px-2 py-1">删除</button>
          </div>
          <details className="text-2xs text-ink-500">
            <summary className="cursor-pointer select-none">细节（身份 / 性格 / 动机 / 秘密 / 重要度）</summary>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <input defaultValue={npc.role || ''} placeholder="身份"
                     onBlur={(e) => onSend('update_npc', npc.name, { role: e.target.value })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-24" />
              <input defaultValue={npc.personality || ''} placeholder="性格"
                     onBlur={(e) => onSend('update_npc', npc.name, { personality: e.target.value })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-24" />
              <input defaultValue={npc.motivation || ''} placeholder="动机"
                     onBlur={(e) => onSend('update_npc', npc.name, { motivation: e.target.value })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-24" />
              <input defaultValue={npc.secret || ''} placeholder="秘密（仅 DM/编辑者可见）"
                     onBlur={(e) => onSend('update_npc', npc.name, { secret: e.target.value })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 flex-1 min-w-[8rem]" />
              <select value={npc.importance || 'minor'}
                      onChange={(e) => onSend('update_npc', npc.name, { importance: e.target.value })}
                      className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
                <option value="minor">简单 NPC</option>
                <option value="major">重要 NPC</option>
              </select>
              <input type="number" defaultValue={npc.ac ?? 10} title="AC"
                     onBlur={(e) => onSend('update_npc', npc.name, { ac: Number(e.target.value) || 0 })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-16" />
              <input type="number" defaultValue={npc.max_hp ?? 10} title="最大 HP"
                     onBlur={(e) => onSend('update_npc', npc.name, { max_hp: Number(e.target.value) || 0 })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-16" />
              <input type="number" defaultValue={npc.level ?? 1} title="等级"
                     onBlur={(e) => onSend('update_npc', npc.name, { level: Number(e.target.value) || 1 })}
                     className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-16" />
            </div>
          </details>
        </div>
      ))}
    </div>
  );
}
