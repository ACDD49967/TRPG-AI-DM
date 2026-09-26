/** 「笔记」页签：线索与对 NPC 的印象（角色视角）。 */
import EmptyState from '../ui/EmptyState';
import type { JournalData } from './types';

export default function NotesPanel({ j, notesCount }: { j: JournalData; notesCount: number }) {
  return (
    <div className="space-y-3">
      {j.character_notes?.quest_clues?.length > 0 && (
        <div>
          <p className="text-2xs text-amber-700 font-semibold mb-1">线索（{j.character_notes.quest_clues.length}）</p>
          {j.character_notes.quest_clues.map((n, i) => (
            <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl p-2.5 mb-1.5 text-xs">
              <p className="text-amber-800 font-medium">{n.target}</p>
              {n.comment && <p className="text-amber-700/80 mt-1 italic text-2xs">“{n.comment}”</p>}
              {n.clue && <p className="text-ink-500 mt-1 text-2xs">线索：{n.clue}</p>}
            </div>
          ))}
        </div>
      )}
      {j.character_notes?.npc_notes?.length > 0 && (
        <div>
          <p className="text-2xs text-emerald-700 font-semibold mb-1 mt-2">印象（{j.character_notes.npc_notes.length}）</p>
          {j.character_notes.npc_notes.map((n, i) => (
            <div key={i} className="bg-emerald-50 border border-emerald-200 rounded-xl p-2.5 mb-1.5 text-xs">
              <p className="text-emerald-800 font-medium">{n.target}</p>
              {n.comment && <p className="text-emerald-700/80 mt-1 italic text-2xs">“{n.comment}”</p>}
            </div>
          ))}
        </div>
      )}
      {notesCount === 0 && (
        <EmptyState icon="📝" title="还没有笔记" hint="与 NPC 互动、记录线索或在对话中产生印象后，这里会自动积累。" />
      )}
    </div>
  );
}
