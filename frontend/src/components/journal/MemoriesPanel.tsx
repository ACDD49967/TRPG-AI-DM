/**
 * 「记忆」页签：系统长期记住的事实（与 DM 的记忆库是同一份数据）。
 *
 * 长期记忆此前**只能创建与检索**：玩家看不到"系统记住了什么"，也没法删掉一条记错的。
 * 后端已补 `/api/memories` 的增删改查，这里给它一个玩家入口——自己取数、自己改自己删，
 * 不占用 `useJournalData` 的装配（那边只负责已有四个页签）。
 */
import { useCallback, useEffect, useState } from 'react';
import { useGameStore } from '../../store/gameStore';
import EmptyState from '../ui/EmptyState';

type Memory = {
  id: string; content: string; memory_type: string;
  importance?: number; updated_at?: string;
};

export default function MemoriesPanel() {
  const username = useGameStore((s) => s.status?.username) || 'default';
  const [items, setItems] = useState<Memory[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [note, setNote] = useState('');
  const [draft, setDraft] = useState('');
  const [editingId, setEditingId] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/memories?username=${encodeURIComponent(username)}&limit=100`);
      const body = await r.json();
      setItems((body.memories || []) as Memory[]);
    } catch {
      setNote('记忆列表加载失败');
    } finally {
      setLoaded(true);
    }
  }, [username]);

  useEffect(() => { void load(); }, [load]);

  const request = async (url: string, init: RequestInit): Promise<boolean> => {
    setBusy(true);
    setNote('');
    try {
      const r = await fetch(url, init);
      if (!r.ok) {
        setNote(r.status === 404 ? '这条记忆已经不在了' : '操作失败，稍后再试');
        return false;
      }
      await load();
      return true;
    } catch {
      setNote('网络错误');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    const content = draft.trim();
    if (!content) return;
    if (editingId) {
      // 改正文等于"删旧写新"（id 是内容哈希），后端会把新记忆整条返回
      if (await request(`/api/memories/${encodeURIComponent(editingId)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, content }),
      })) { setDraft(''); setEditingId(''); }
      return;
    }
    if (await request('/api/memories', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, content, memory_type: 'semantic', source: 'journal' }),
    })) setDraft('');
  };

  const remove = async (id: string) => {
    if (!window.confirm('删掉这条记忆？系统以后不会再据此推进剧情。')) return;
    await request(`/api/memories/${encodeURIComponent(id)}?username=${encodeURIComponent(username)}`,
                  { method: 'DELETE' });
  };

  return (
    <div className="space-y-2">
      <p className="text-2xs text-ink-500 leading-relaxed">
        这里列出主持系统长期记住的事实；「改写」等于重记一条（旧记录会被替换）。
      </p>
      <div className="flex gap-1.5">
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
               placeholder="新增或改写一条记忆…"
               aria-label="记忆正文"
               className="flex-1 text-2xs px-2 py-1.5 min-h-[40px] rounded-lg border border-ink-200" />
        <button onClick={() => void submit()} disabled={busy}
                className="text-2xs px-2.5 min-h-[40px] rounded-lg border border-brand-200 bg-brand-50
                           text-brand-700 hover:bg-brand-100 disabled:opacity-50">
          {editingId ? '保存' : '新增'}
        </button>
      </div>
      {note && <p className="text-2xs text-amber-700">{note}</p>}
      {items.map((m) => (
        <div key={m.id} className="bg-white/70 border border-ink-200 rounded-xl p-2 text-xs">
          <p className="text-ink-800 leading-relaxed">{m.content}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="tag-gray">{m.memory_type}</span>
            <span className="text-3xs text-ink-400 font-mono">{(m.updated_at || '').slice(0, 10)}</span>
            <span className="flex-1" />
            <button onClick={() => { setDraft(m.content); setEditingId(m.id); }} disabled={busy}
                    className="text-2xs text-brand-600 px-2 min-h-[28px] rounded-lg hover:bg-brand-50">
              改写
            </button>
            <button onClick={() => void remove(m.id)} disabled={busy}
                    className="text-2xs text-red-600 px-2 min-h-[28px] rounded-lg hover:bg-red-50">
              删除
            </button>
          </div>
        </div>
      ))}
      {loaded && items.length === 0 && !note && (
        <EmptyState icon="🧠" title="还没有长期记忆" hint="重要事实、暗线与人物影响会由主持自动记到这里。" />
      )}
    </div>
  );
}
