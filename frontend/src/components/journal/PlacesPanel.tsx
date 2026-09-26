/** 「地点」页签：已发现地点 + 图鉴里的公开详情（不含秘密）。 */
import EmptyState from '../ui/EmptyState';
import type { MapsDetail } from './useJournalData';
import type { JournalData } from './types';

export default function PlacesPanel({ j, mapsDetail }: {
  j: JournalData;
  mapsDetail: MapsDetail;
}) {
  return (
    <div className="space-y-1.5">
      {j.locations.map((l) => {
        const detail = mapsDetail.find((m) => m.name === l.name);
        return (
          <details key={l.name} className="group bg-white rounded-xl px-2.5 py-2 border border-ink-200 text-xs">
            <summary className="cursor-pointer select-none flex items-center justify-between gap-2">
              {/* 名称不截断（改为换行）：侧栏只有约 180px 宽，
                  "维尔德庄园·暖光走廊（前厅内侧）"与"（右侧门影处）"截断后长得一模一样，
                  玩家会以为出现了重复卡片。 */}
              <span className="text-ink-700 font-medium min-w-0 break-words" title={l.name}>{l.name}</span>
              <span className="text-2xs text-ink-400 shrink-0 flex items-center gap-1">
                {detail?.details?.type || '地点'} · {detail?.details?.status || l.status || '未知'}
                <svg viewBox="0 0 20 20" fill="none" className="w-3 h-3 transition-transform group-open:rotate-180" aria-hidden>
                  <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </summary>
            <div className="mt-2 pt-2 border-t border-ink-100 space-y-1 text-2xs text-ink-600 leading-relaxed">
              {l.description && <p>{l.description}</p>}
              {l.type && <p>类型：{l.type}</p>}
              {l.culture && <p>文化/势力：{l.culture}</p>}
              {l.notable_figures && <p>知名人物：{l.notable_figures}</p>}
              {l.dangers && <p className="text-red-700">危险：{l.dangers}</p>}
              {l.related_npcs && l.related_npcs.length > 0 && <p>关联角色：{l.related_npcs.join('、')}</p>}
              {l.related_creatures && l.related_creatures.length > 0 && <p>关联生物：{l.related_creatures.join('、')}</p>}
              {l.related_locations && l.related_locations.length > 0 && <p>相邻/关联地点：{l.related_locations.join('、')}</p>}
              {!l.type && detail?.details?.culture && <p>文化/势力：{detail.details.culture}</p>}
              {!l.type && detail?.details?.districts && detail.details.districts.length > 0 && (
                <p>区域：{detail.details.districts.join('、')}</p>
              )}
              {!l.type && detail?.details?.notable_figures && <p>知名人物：{detail.details.notable_figures}</p>}
              {!l.type && detail?.details?.dangers && <p className="text-red-700">危险：{detail.details.dangers}</p>}
              {l.secret && <p className="text-red-600">已揭示秘密：{l.secret}</p>}
              {/* 这行是"什么资料都没有"时的占位。条件里必须带上 !l.description：
                  否则 description 会在上面印一遍、这里再印一遍（实测地点卡整段文字重复）。
                  图鉴里有这条地点时上面已经用 detail 补过字段，也不该再提示未知。 */}
              {!l.description && !l.type && !detail && <p className="text-ink-400">未知地点</p>}
            </div>
          </details>
        );
      })}
      {j.locations.length === 0 && (
        <EmptyState icon="🗺️" title="还没有标记地点" hint="抵达或发现新地点后，这里会记录名称、状态、危险与关联角色。" />
      )}
    </div>
  );
}
