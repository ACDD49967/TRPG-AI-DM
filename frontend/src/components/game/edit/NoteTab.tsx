/** 笔记标签页：角色视角笔记（NPC 印象 / 事件 / 线索 / 地点）的增删改与可见性。 */
import { useState } from 'react';
import type { SendWorld, WorldState } from './types';

const TYPES: Array<[string, string]> = [
  ['npc', 'NPC 印象'], ['event', '事件'], ['quest', '线索'], ['location', '地点'],
];
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPES);

export default function NoteTab({ world, busy, onSend }: {
  world: WorldState; busy: boolean; onSend: SendWorld;
}) {
  const notes = world.notes || [];
  const [target, setTarget] = useState('');
  const [noteType, setNoteType] = useState('npc');
  const [comment, setComment] = useState('');
  const [clue, setClue] = useState('');

  const add = () => {
    const name = target.trim();
    if (!name) return;
    onSend('add_note', name, {
      target_type: noteType, comment: comment.trim(), clue: clue.trim(), visible: true,
    });
    setTarget(''); setComment(''); setClue('');
  };

  return (
    <div className="space-y-2">
      <div className="border border-dashed border-ink-200 rounded-xl p-2 space-y-1.5">
        <p className="text-2xs text-ink-500">添加笔记（角色视角的一句话印象 / 线索）</p>
        <div className="flex gap-1.5 flex-wrap">
          <input value={target} onChange={(e) => setTarget(e.target.value)}
                 placeholder="针对谁 / 哪件事"
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-36" />
          <select value={noteType} onChange={(e) => setNoteType(e.target.value)}
                  className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
            {TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="角色视角评价"
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 flex-1 min-w-[8rem]" />
          <input value={clue} onChange={(e) => setClue(e.target.value)} placeholder="线索 / 推论"
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 flex-1 min-w-[8rem]" />
          <button disabled={busy || !target.trim()} onClick={add}
                  className="text-2xs px-3 py-1 rounded-lg border border-ink-200 disabled:opacity-50">
            添加
          </button>
        </div>
      </div>

      {notes.map((note) => (
        <div key={`${note.target_type}:${note.target}`} data-note-target={note.target}
             className="border border-ink-200 rounded-xl p-2 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-800">{note.target}</span>
            <span className="text-3xs text-ink-400">
              {TYPE_LABEL[note.target_type || 'npc'] || note.target_type}
            </span>
            <span className="flex-1" />
            <label className="text-3xs text-ink-500 flex items-center gap-1">
              <input type="checkbox" checked={note.visible !== false}
                     onChange={(e) => onSend('update_note', note.target,
                       { target_type: note.target_type, visible: e.target.checked })} />
              玩家可见
            </label>
            <button onClick={() => onSend('remove_character_note', note.target,
                                          { target_type: note.target_type })}
                    className="text-2xs text-red-700 px-2 py-1">删除</button>
          </div>
          <input defaultValue={note.comment || ''} placeholder="角色视角评价"
                 onBlur={(e) => onSend('update_note', note.target,
                   { target_type: note.target_type, comment: e.target.value })}
                 className="w-full text-2xs px-2 py-1 rounded-lg border border-ink-200" />
          <input defaultValue={note.clue || ''} placeholder="线索 / 推论"
                 onBlur={(e) => onSend('update_note', note.target,
                   { target_type: note.target_type, clue: e.target.value })}
                 className="w-full text-2xs px-2 py-1 rounded-lg border border-ink-200" />
        </div>
      ))}
      {notes.length === 0 && <p className="text-2xs text-ink-400">还没有笔记。</p>}
    </div>
  );
}
