/** 单条地点卡：折叠头、行内编辑、详情与关联生物。 */
import InlineEdit from '../../ui/InlineEdit';
import { deleteMediaItem } from '../mediaActions/deleteMedia';

export default function MapEntryCard({
  m, bestiary, q, status, setMaps,
}: {
  m: any;
  bestiary: any[];
  q: (text: any) => string;
  status: any;
  setMaps: (updater: any) => void;
}) {
  const relatedCreatures = bestiary.filter((b: any) =>
    q(`${b.description} ${b.details?.habitat || ''} ${b.details?.lore || ''}`).includes(q(m.name)));
  return (
    <details className="group entry-card mb-3">
      <summary className="entry-summary">
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-bold truncate">{m.name}</span>
          <span className={`scope-badge ${m.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{m.scenario_id ? '当前剧本' : '通用参考'}</span>
        </span>
        <span className="text-[9px] text-ink-400 shrink-0">
          {m.details?.type || '地点'} · {m.details?.status || '未知'} · {m.locations.length} 子地点
          <span className="ml-1 group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span>
        </span>
      </summary>
      <div className="px-3 pb-3 border-t border-gray-100">
        <div className="flex justify-end mb-1">
          <InlineEdit
            label="编辑地点"
            fields={[
              { key: 'name', label: '名称', value: m.name || '' },
              { key: 'description', label: '描述', value: m.description || '', type: 'textarea' },
            ]}
            onSave={async (values) => {
              const u = (status?.username as string) || 'default';
              const response = await fetch(
                `/api/maps/${encodeURIComponent(m.id)}?username=${encodeURIComponent(u)}`,
                {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ name: values.name, description: values.description }),
                });
              if (!response.ok) return;
              const body = await response.json();
              setMaps((prev: any[]) => prev.map((item) =>
                item.id === m.id ? { ...item, ...(body.map || {}) } : item));
            }}
          >
            <span className="text-[10px] text-ink-500">编辑名称与描述</span>
          </InlineEdit>
          <button
            type="button"
            className="text-[10px] text-red-600 hover:text-red-700 ml-2 shrink-0 px-1.5 min-h-[28px]"
            onClick={async () => {
              if (!window.confirm(`确定删除地点「${m.name}」？此操作不可恢复。`)) return;
              if (await deleteMediaItem('map', m.id, status?.username)) {
                setMaps((prev: any[]) => prev.filter((item) => item.id !== m.id));
              }
            }}
          >
            删除
          </button>
        </div>
        {m.image_path && <img src={m.image_path} alt={m.name} className="w-full max-h-80 object-contain bg-gray-100 mb-2" />}
        <p className="text-[10px] text-ink-500 mb-2">{m.description_zh || m.description}{m.description_zh && m.description ? <span className="text-ink-400 italic">（原文：{m.description.slice(0, 60)}...）</span> : null}</p>
        {m.locations.length > 0 && <div className="flex flex-wrap gap-1 mb-2">{m.locations.map((l: any, i: any) => <span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-100">{l.name}</span>)}</div>}
        {m.details && (
          <div className="text-[10px] text-ink-600 space-y-1">
            {m.details.type && <p>类型：{m.details.type}</p>}
            {m.details.status && <p>状态：{m.details.status}</p>}
            {m.details.culture && <p>文化/势力：{m.details.culture}</p>}
            {m.details.districts && m.details.districts.length > 0 && <p>区域：{m.details.districts.join('、')}</p>}
            {m.details.notable_figures && <p>知名人物：{m.details.notable_figures}</p>}
            {m.details.dangers && <p>危险：{m.details.dangers}</p>}
          </div>
        )}
        {relatedCreatures.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-100">
            <p className="text-[9px] text-ink-400 mb-1">可能出现的生物</p>
            <div className="flex flex-wrap gap-1">{relatedCreatures.map((b: any) => <span key={b.id} className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-1.5 py-0.5">{b.name}</span>)}</div>
          </div>
        )}
      </div>
    </details>
  );
}
