/** 「角色场景」页签：敌人/盟友/其他 + 值得注意的场景与物品。 */
import EmptyState from '../ui/EmptyState';
import { NpcCard } from './npcCards';
import type { JournalData } from './types';

export default function NpcPanel({ j, npcs, notableCount }: {
  j: JournalData;
  npcs: JournalData['npcs'];
  notableCount: number;
}) {
  return (
    <>
      {npcs.enemies.length > 0 && (
        <div>
          <p className="text-2xs text-red-700 font-semibold mb-1">敌人（{npcs.enemies.length}）</p>
          {npcs.enemies.map((n) => <NpcCard key={n.name} npc={n} cat="enemy" />)}
        </div>
      )}
      {npcs.allies.length > 0 && (
        <div>
          <p className="text-2xs text-emerald-700 font-semibold mb-1 mt-2">盟友（{npcs.allies.length}）</p>
          {npcs.allies.map((n) => <NpcCard key={n.name} npc={n} cat="ally" />)}
        </div>
      )}
      {npcs.neutrals.length > 0 && (
        <div>
          <p className="text-2xs text-ink-400 font-semibold mb-1 mt-2">其他（{npcs.neutrals.length}）</p>
          {npcs.neutrals.map((n) => <NpcCard key={n.name} npc={n} cat="neutral" />)}
        </div>
      )}
      {notableCount > 0 && (
        <div className="mt-2">
          <p className="text-2xs text-sky-700 font-semibold mb-1">场景 / 物品（{notableCount}）</p>
          {j.notables!.map((n, i) => (
            <div key={i} className="bg-white rounded-xl p-2 border border-ink-200 text-xs mb-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-ink-700 font-medium truncate">{n.name}</span>
                <span className="text-3xs text-amber-700 shrink-0">
                  {n.entry_type}
                  {n.importance === 'major' ? ' · 重要' : ''}
                </span>
              </div>
              {n.description && <p className="text-2xs text-ink-500 mt-1 leading-relaxed">{n.description}</p>}
              {(n.location || n.status) && (
                <p className="text-3xs text-ink-400 mt-1">{[n.location, n.status].filter(Boolean).join(' · ')}</p>
              )}
            </div>
          ))}
        </div>
      )}
      {npcs.total === 0 && notableCount === 0 && (
        <EmptyState icon="👥" title="还没有遇到值得记录的人物" hint="随着剧情推进，DM 会把已发现的 NPC、场景与物品自动记到笔记里。" />
      )}
    </>
  );
}
