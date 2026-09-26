/** 单条法术卡：折叠头、行内编辑与施法参数/描述。 */
import InlineEdit from '../../ui/InlineEdit';
import { deleteMediaItem } from '../mediaActions/deleteMedia';

export default function SpellEntryCard({
  s, status, setSpells,
}: {
  s: any;
  status: any;
  setSpells: (updater: any) => void;
}) {
  return (
    <details className="group entry-card p-2.5 mb-2">
      <summary className="cursor-pointer select-none flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <span className="paper-title text-sm font-bold truncate">{s.name_zh || s.name}：{Number(s.level) === 0 ? '戏法' : `${s.level}环`} {s.school}{s.name_zh && s.name_zh !== s.name ? <span className="text-ink-400 font-normal">（{s.name}）</span> : null}</span>
          <span className={`scope-badge ${s.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{s.scenario_id ? '当前剧本' : '通用参考'}</span>
        </span>
        <span className="text-[9px] text-ink-400 shrink-0">{s.ritual ? '仪式 · ' : ''}{s.classes.length > 0 ? `${s.classes.join('、')} · ` : ''}<span className="group-open:hidden">▸ 详情</span><span className="hidden group-open:inline">▾</span></span>
      </summary>
      <div className="mt-2 pt-2 border-t border-amber-900/10 text-[10px] text-ink-600 space-y-1">
        <div className="flex justify-end">
          <InlineEdit
            label="编辑法术"
            fields={[
              { key: 'name', label: '名称', value: s.name || '' },
              { key: 'level', label: '环位', value: String(s.level ?? ''), type: 'number' },
              { key: 'description', label: '描述', value: s.description || '', type: 'textarea' },
            ]}
            onSave={async (values) => {
              const u = (status?.username as string) || 'default';
              const response = await fetch(
                `/api/spells/${encodeURIComponent(s.id)}?username=${encodeURIComponent(u)}`,
                {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    name: values.name,
                    level: values.level,
                    description: values.description,
                  }),
                });
              if (!response.ok) return;
              const body = await response.json();
              setSpells((prev: any[]) => prev.map((item) =>
                item.id === s.id ? { ...item, ...(body.spell || {}) } : item));
            }}
          >
            <span className="text-[10px] text-ink-500">编辑名称 / 环位 / 描述</span>
          </InlineEdit>
          <button
            type="button"
            className="text-[10px] text-red-600 hover:text-red-700 ml-2 shrink-0 px-1.5 min-h-[28px]"
            onClick={async () => {
              if (!window.confirm(`确定删除法术「${s.name}」？此操作不可恢复。`)) return;
              if (await deleteMediaItem('spell', s.id, status?.username)) {
                setSpells((prev: any[]) => prev.filter((item) => item.id !== s.id));
              }
            }}
          >
            删除
          </button>
        </div>
        {s.casting_time && <p><span className="text-ink-400">施法时间：</span>{s.casting_time}</p>}
        {s.range && <p><span className="text-ink-400">施法距离：</span>{s.range}</p>}
        {s.components && <p><span className="text-ink-400">法术成分：</span>{s.components}</p>}
        {s.duration && <p><span className="text-ink-400">持续时间：</span>{s.duration}</p>}
        {(s.description_zh || s.description) && <p className="text-ink-700 whitespace-pre-line">{s.description_zh || s.description}</p>}
        {s.description_zh && s.description && <p className="text-ink-400 italic whitespace-pre-line">原文：{s.description}</p>}
      </div>
    </details>
  );
}
