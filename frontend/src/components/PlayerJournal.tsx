/**
 * 冒险笔记（右侧栏）—— 角色和场景 / 剧情 / 地点 / 笔记
 *
 * 优化点：
 *  - 字号从 7~10px 抬升到 11~12px，NPC 数值面板不再需要凑近屏幕。
 *  - 标签页带条目计数与空状态提示，玩家知道「是没内容还是没加载」。
 *  - NPC 卡片统一展开箭头与数值网格，未揭示内容保持 ??? 语义不变。
 *  - 作为移动端抽屉使用时占满宽度（w-full md:w-72）。
 *
 * 数据在 `journal/useJournalData`，四个页签各自成组件（`journal/*Panel`）。
 */
import NotesPanel from './journal/NotesPanel';
import MemoriesPanel from './journal/MemoriesPanel';
import NpcPanel from './journal/NpcPanel';
import PlacesPanel from './journal/PlacesPanel';
import PlotPanel from './journal/PlotPanel';
import { useJournalData, type JournalTab } from './journal/useJournalData';

const TAB_LABELS: Record<JournalTab, string> = {
  npcs: '角色场景', plot: '剧情', places: '地点', notes: '笔记', memories: '记忆',
};

export default function PlayerJournal() {
  const data = useJournalData();
  if (!data.ready) return null;
  const { j, tab, setTab, mapsDetail, journalStatus, npcs, notableCount, notesCount, tabCount } = data;

  const syncChip =
    journalStatus === 'syncing' ? (
      <span className="tag-amber ml-auto"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse-soft" aria-hidden />同步中</span>
    ) : journalStatus === 'synced' ? (
      <span className="tag-green ml-auto">已同步</span>
    ) : (
      <span className="tag-gray ml-auto">待同步</span>
    );

  return (
    <aside className="w-full md:w-72 flex-shrink-0 bg-ink-50/70 md:border-l border-ink-200 flex flex-col overflow-hidden">
      {/* 标题栏 */}
      <div className="px-3 py-2.5 border-b border-ink-200 bg-white/70 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="text-brand-600 font-bold text-xs">冒险笔记</span>
          {j.turn_count > 0 && <span className="text-2xs text-ink-400 font-mono">第 {j.turn_count} 轮</span>}
          {syncChip}
        </div>
        {j.scene?.atmosphere && <p className="text-2xs text-ink-400 italic mt-1 leading-relaxed">{j.scene.atmosphere}</p>}
      </div>

      {/* 标签页 */}
      <div className="flex border-b border-ink-200 bg-white/60 px-1 no-scrollbar overflow-x-auto">
        {(Object.keys(TAB_LABELS) as JournalTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            aria-selected={tab === t}
            role="tab"
            /* 五个页签在 288px 的侧栏里放不下（实测溢出 41px，"角色场景"被截成"场景"）：
               改成按内容伸缩（flex-1 + min-w-0），不再强制 64px 最小宽度 */
            className={`flex-1 min-w-0 px-1 py-2 min-h-[40px] text-2xs text-center whitespace-nowrap transition-colors border-b-2 ${
              tab === t
                ? 'text-brand-700 border-brand-500 font-semibold'
                : 'text-ink-400 border-transparent hover:text-ink-600'
            }`}
          >
            {TAB_LABELS[t]}
            {(tabCount[t] || 0) > 0 && <span className="ml-1 font-mono text-3xs text-ink-400">{tabCount[t]}</span>}
          </button>
        ))}
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2" role="tabpanel">
        {tab === 'npcs' && <NpcPanel j={j} npcs={npcs} notableCount={notableCount} />}
        {tab === 'plot' && <PlotPanel j={j} />}
        {tab === 'places' && <PlacesPanel j={j} mapsDetail={mapsDetail} />}
        {tab === 'notes' && <NotesPanel j={j} notesCount={notesCount} />}
        {tab === 'memories' && <MemoriesPanel />}
      </div>
    </aside>
  );
}
