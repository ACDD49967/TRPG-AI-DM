/** 「剧情」页签：世界动态/传闻 + 剧情旗标状态。 */
import EmptyState from '../ui/EmptyState';
import type { JournalData } from './types';

export default function PlotPanel({ j }: { j: JournalData }) {
  return (
    <div className="space-y-2">
      {j.world_events && j.world_events.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-2.5">
          <p className="text-2xs text-amber-700 font-semibold mb-1">世界动态 / 传闻</p>
          {j.world_events.map((w, i) => (
            <p key={i} className="text-2xs text-ink-600 mt-1 leading-relaxed">· {w.text}</p>
          ))}
        </div>
      )}
      {j.plot_flags.map((f) => (
        <div key={f.key} className="bg-white rounded-xl p-2.5 border border-ink-200 text-xs">
          <div className="flex items-center gap-1.5">
            <span
              className={
                f.status === '已完成' ? 'text-emerald-600' : f.status === '进行中' ? 'text-sky-700' : 'text-ink-400'
              }
              aria-hidden
            >
              ●
            </span>
            <span className="text-ink-700 font-medium">{f.key}</span>
            <span className="ml-auto text-3xs text-ink-400">{f.status}</span>
          </div>
          {f.description && <p className="text-2xs text-ink-400 mt-1 ml-4 leading-relaxed">{f.description}</p>}
        </div>
      ))}
      {j.plot_flags.length === 0 && (j.world_events?.length || 0) === 0 && (
        <EmptyState icon="🧭" title="剧情线尚未展开" hint="推进剧情后，主线线索、任务状态与世界动态会在这里汇总。" />
      )}
    </div>
  );
}
