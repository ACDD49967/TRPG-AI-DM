/**
 * 冒险笔记（右侧栏）—— 角色和场景 / 剧情 / 地点 / 笔记
 *
 * 优化点：
 *  - 字号从 7~10px 抬升到 11~12px，NPC 数值面板不再需要凑近屏幕。
 *  - 标签页带条目计数与空状态提示，玩家知道「是没内容还是没加载」。
 *  - NPC 卡片统一展开箭头与数值网格，未揭示内容保持 ??? 语义不变。
 *  - 作为移动端抽屉使用时占满宽度（w-full md:w-72）。
 */

import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { textValue } from '../utils/textValue';
import EmptyState from './ui/EmptyState';

interface CharNote { target: string; comment: string; clue?: string; turn: number }
interface NpcView {
  name: string; race: string; role: string; attitude: string; alive: boolean | null;
  appearance: string; personality: string; motivation: string; secret: string; relation_to_plot: string;
  location: string; level?: number; ac?: number; hp?: number; max_hp?: number;
  attributes?: Record<string, number>; skills?: string[]; traits?: string[]; equipment?: string[];
  related_locations?: string[]; related_npcs?: string[]; related_creatures?: string[];
  image_path?: string; importance?: 'major' | 'minor' | string; fully_revealed: boolean;
}
interface JournalData {
  scene: { location: string; time: string; weather: string; atmosphere: string; npcs_here: string[] };
  npcs: { allies: NpcView[]; enemies: NpcView[]; neutrals: NpcView[]; total: number };
  plot_flags: { key: string; status: string; description: string }[];
  world_events?: { turn?: number; text: string }[];
  locations: Array<{
    name: string; description: string; status: string; secret?: string; type?: string; culture?: string;
    notable_figures?: string; dangers?: string; related_locations?: string[]; related_npcs?: string[]; related_creatures?: string[];
  }>;
  character_notes: { npc_notes: CharNote[]; event_notes: CharNote[]; quest_clues: CharNote[]; location_notes: CharNote[] };
  notables?: Array<{ name: string; entry_type: string; description: string; location?: string; status?: string; importance?: string; tags?: string[]; image_path?: string }>;
  turn_count: number;
}

const CAT_COLORS: Record<string, string> = {
  ally: 'border-emerald-200 bg-emerald-50/50',
  enemy: 'border-red-200 bg-red-50/50',
  neutral: 'border-ink-200 bg-ink-50/60',
};
const CAT_LABELS: Record<string, string> = { ally: '友善', enemy: '敌对', neutral: '中立' };
const ATTR_NAMES: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
  pow: '意志', siz: '体型', edu: '教育',
};
const mod = (v: number) => `${Math.floor((v - 10) / 2) >= 0 ? '+' : ''}${Math.floor((v - 10) / 2)}`;

function Row({ k, v, c }: { k: string; v?: string; c?: string }) {
  if (!v) return null;
  const hidden = v === '???';
  return (
    <div className="flex gap-1.5 text-2xs leading-relaxed">
      <span className="text-ink-400 shrink-0">{k}：</span>
      <span className={c || (hidden ? 'text-ink-400 italic' : 'text-ink-600')}>{hidden ? '???' : v}</span>
    </div>
  );
}

/** 数值网格：HP/AC/Lv 或六维属性 */
function StatGrid({ npc }: { npc: NpcView }) {
  const tiles: Array<[string, string]> = [];
  if (npc.hp != null && npc.max_hp != null) tiles.push(['HP', `${npc.hp}/${npc.max_hp}`]);
  if (npc.ac != null) tiles.push(['AC', String(npc.ac)]);
  if (npc.level != null) tiles.push(['Lv', String(npc.level)]);
  if (tiles.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-1">
      {tiles.map(([k, v]) => (
        <div key={k} className="bg-white rounded-lg px-1.5 py-1 border border-ink-200 text-center">
          <span className="text-3xs text-ink-400">{k}</span>
          <span className="ml-1 font-mono font-bold text-2xs text-ink-800">{v}</span>
        </div>
      ))}
    </div>
  );
}

function AttrGrid({ attrs, size = 'sm' }: { attrs: Record<string, number>; size?: 'sm' | 'lg' }) {
  const entries = Object.entries(attrs);
  if (entries.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-x-1 gap-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="text-center leading-tight">
          <p className="text-3xs uppercase tracking-wide text-ink-400">{ATTR_NAMES[k] || k}</p>
          <p className={`font-bold ${size === 'lg' ? 'text-xs' : 'text-2xs'}`}>
            {textValue(v)}
            <span className="ml-0.5 text-3xs text-ink-400 font-normal">({mod(Number(v))})</span>
          </p>
        </div>
      ))}
    </div>
  );
}

function NpcCard({ npc, cat }: { npc: NpcView; cat: string }) {
  return (
    <details className={`group rounded-xl border p-2 ${CAT_COLORS[cat] || CAT_COLORS.neutral} text-xs mb-1`}>
      <summary className="cursor-pointer select-none">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            {npc.image_path ? (
              <img src={npc.image_path} alt={npc.name} loading="lazy" className="w-6 h-6 rounded-md object-cover border border-ink-200 shrink-0" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-40 shrink-0" aria-hidden />
            )}
            <span className="font-bold text-ink-800 truncate">{npc.name}</span>
            {npc.importance === 'major' && <span className="tag-amber shrink-0">重要</span>}
          </div>
          <span className="text-2xs text-ink-400 shrink-0 flex items-center gap-1">
            {npc.hp != null && npc.max_hp != null && <span className="font-mono">HP {npc.hp}/{npc.max_hp}</span>}
            {npc.ac != null && <span className="font-mono">AC {npc.ac}</span>}
            <svg viewBox="0 0 20 20" fill="none" className={`w-3 h-3 transition-transform ${'group-open:rotate-180'}`} aria-hidden>
              <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </div>
      </summary>

      {!npc.fully_revealed ? (
        /* 未完全揭示：只给玩家已知信息 */
        <div className="mt-2 pt-2 border-t border-ink-200/70 space-y-1.5">
          <Row k="身份" v={npc.role} />
          {npc.race && npc.race !== '???' && <Row k="种族" v={npc.race} />}
          {npc.location && <Row k="位置" v={npc.location} />}
          <StatGrid npc={npc} />
          {npc.attributes && Object.keys(npc.attributes).length > 0 && (
            <div className="pt-1.5 border-t border-ink-200/70">
              <AttrGrid attrs={npc.attributes} />
            </div>
          )}
          {npc.skills && npc.skills.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">技能 </span>
              {npc.skills.map(textValue).join('、')}
            </p>
          )}
          {npc.traits && npc.traits.length > 0 && (
            <div className="pt-1.5 border-t border-ink-200/70">
              <p className="text-3xs font-bold text-ink-500">特性 / 动作</p>
              {npc.traits.map((t, i) => (
                <p key={i} className="text-2xs text-ink-700">· {t}</p>
              ))}
            </div>
          )}
          {npc.equipment && npc.equipment.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">装备 </span>
              {npc.equipment.join('、')}
            </p>
          )}
          {npc.related_locations && npc.related_locations.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联地点 </span>
              {npc.related_locations.join('、')}
            </p>
          )}
          {npc.related_npcs && npc.related_npcs.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联角色 </span>
              {npc.related_npcs.join('、')}
            </p>
          )}
          {npc.related_creatures && npc.related_creatures.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联生物 </span>
              {npc.related_creatures.join('、')}
            </p>
          )}
        </div>
      ) : (
        /* 完全揭示：D&D 官方 NPC 卡样式 */
        <div className="mt-2 pt-2 border-t-2 border-parch-600/60 bg-parch-50 rounded-lg px-2.5 py-2">
          <p className="text-center font-bold text-ink-900 text-sm">{npc.name}</p>
          <p className="text-center text-2xs text-ink-500 italic mt-0.5">
            {npc.role || '未知身份'}
            {npc.race && npc.race !== '???' ? ` · ${npc.race}` : ''} · {npc.alive === false ? '已故' : CAT_LABELS[cat]}
          </p>
          <div className="paper-rule my-2" />
          <div className="flex justify-between gap-2 text-2xs">
            <span><b className="text-ink-500 font-medium">护甲等级</b> <b className="font-mono">{npc.ac}</b></span>
            <span><b className="text-ink-500 font-medium">生命值</b> <b className="font-mono">{npc.hp}/{npc.max_hp}</b></span>
            <span><b className="text-ink-500 font-medium">等级</b> <b className="font-mono">{npc.level}</b></span>
          </div>
          {npc.location && <p className="text-2xs text-ink-500 mt-1">位置：{npc.location}</p>}
          {npc.attributes && Object.keys(npc.attributes).length > 0 && (
            <>
              <div className="paper-rule my-2" />
              <AttrGrid attrs={npc.attributes} size="lg" />
            </>
          )}
          {npc.skills && npc.skills.length > 0 && (
            <>
              <div className="paper-rule my-2" />
              <p className="text-2xs"><span className="font-bold text-ink-500">技能 </span>{npc.skills.map(textValue).join('、')}</p>
            </>
          )}
          {npc.traits && npc.traits.length > 0 && (
            <>
              <div className="paper-rule my-2" />
              <p className="text-3xs font-bold text-ink-500">特性 / 动作</p>
              {npc.traits.map((t, i) => (
                <p key={i} className="text-2xs text-ink-700">· {t}</p>
              ))}
            </>
          )}
          {npc.equipment && npc.equipment.length > 0 && (
            <>
              <div className="paper-rule my-2" />
              <p className="text-2xs"><span className="font-bold text-ink-500">装备 </span>{npc.equipment.join('、')}</p>
            </>
          )}
          {(npc.related_locations?.length || npc.related_npcs?.length || npc.related_creatures?.length) ? (
            <>
              <div className="paper-rule my-2" />
              {npc.related_locations && npc.related_locations.length > 0 && (
                <p className="text-2xs"><span className="font-bold text-ink-500">关联地点 </span>{npc.related_locations.join('、')}</p>
              )}
              {npc.related_npcs && npc.related_npcs.length > 0 && (
                <p className="text-2xs"><span className="font-bold text-ink-500">关联角色 </span>{npc.related_npcs.join('、')}</p>
              )}
              {npc.related_creatures && npc.related_creatures.length > 0 && (
                <p className="text-2xs"><span className="font-bold text-ink-500">关联生物 </span>{npc.related_creatures.join('、')}</p>
              )}
            </>
          ) : null}
          <div className="paper-rule my-2" />
          <Row k="外貌" v={npc.appearance} />
          <Row k="性格" v={npc.personality} c="text-brand-600" />
          <Row k="动机" v={npc.motivation} c="text-amber-700" />
          <Row k="秘密" v={npc.secret} c="text-red-700" />
          <Row k="关联" v={npc.relation_to_plot} c="text-sky-700" />
        </div>
      )}
    </details>
  );
}

type TabKey = 'npcs' | 'plot' | 'places' | 'notes';
const TAB_LABELS: Record<TabKey, string> = { npcs: '角色场景', plot: '剧情', places: '地点', notes: '笔记' };

export default function PlayerJournal() {
  const storeJournalData = useGameStore((s) => s.journalData);
  const { sessionId, isProcessing, status } = useGameStore();
  const journalStatus = useGameStore((s) => s.journalStatus);
  const [j, setJ] = useState<JournalData | null>(null);
  const [tab, setTab] = useState<TabKey>('npcs');
  const [mapsDetail, setMapsDetail] = useState<Array<{ name: string; description?: string; details?: { type?: string; status?: string; culture?: string; districts?: string[]; notable_figures?: string; dangers?: string } }>>([]);

  // P2-12修复：优先使用SSE推送的journalData；fallback到API轮询
  useEffect(() => {
    if (storeJournalData) {
      setJ(storeJournalData as unknown as JournalData);
    }
  }, [storeJournalData]);

  // Fallback: SSE不可用时仍做API轮询
  useEffect(() => {
    if (sessionId && !storeJournalData) {
      fetch(`/api/game/${sessionId}/journal?username=${encodeURIComponent(status.username || 'default')}`)
        .then((r) => r.json())
        .then(setJ)
        .catch(() => {});
    }
  }, [sessionId]);
  useEffect(() => {
    if (!isProcessing && sessionId && !storeJournalData) {
      fetch(`/api/game/${sessionId}/journal?username=${encodeURIComponent(status.username || 'default')}`)
        .then((r) => r.json())
        .then(setJ)
        .catch(() => {});
    }
  }, [isProcessing, sessionId]);

  // 关联地点图鉴：右侧「地点」页合并图鉴公开详情（不含秘密）
  useEffect(() => {
    const u = status.username || 'default';
    const sid = status.scenario_id || '';
    fetch(`/api/maps?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`)
      .then((r) => r.json())
      .then((d) => {
        // 显示当前剧本关联地点 + 通用参考地点；隐藏其它剧本
        const all = d.maps || [];
        if (!sid) {
          setMapsDetail([]);
          return;
        }
        setMapsDetail(all.filter((m: { scenario_id?: string }) => !m.scenario_id || m.scenario_id === sid));
      })
      .catch(() => {});
  }, [status.username, status.scenario_id]);

  if (!j || !j.npcs) return null;

  const { npcs } = j;
  const notableCount = j.notables?.length || 0;
  const notesCount =
    (j.character_notes?.quest_clues?.length || 0) + (j.character_notes?.npc_notes?.length || 0);

  const tabCount: Record<TabKey, number> = {
    npcs: npcs.total + notableCount,
    plot: j.plot_flags.length + (j.world_events?.length || 0),
    places: j.locations.length,
    notes: notesCount,
  };

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
        {(Object.keys(TAB_LABELS) as TabKey[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            aria-selected={tab === t}
            role="tab"
            className={`flex-1 min-w-[64px] py-2 text-2xs text-center whitespace-nowrap transition-colors border-b-2 ${
              tab === t
                ? 'text-brand-700 border-brand-500 font-semibold'
                : 'text-ink-400 border-transparent hover:text-ink-600'
            }`}
          >
            {TAB_LABELS[t]}
            {tabCount[t] > 0 && <span className="ml-1 font-mono text-3xs text-ink-400">{tabCount[t]}</span>}
          </button>
        ))}
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2" role="tabpanel">
        {tab === 'npcs' && (
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
        )}

        {tab === 'plot' && (
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
        )}

        {tab === 'places' && (
          <div className="space-y-1.5">
            {j.locations.map((l) => {
              const detail = mapsDetail.find((m) => m.name === l.name);
              return (
                <details key={l.name} className="group bg-white rounded-xl px-2.5 py-2 border border-ink-200 text-xs">
                  <summary className="cursor-pointer select-none flex items-center justify-between gap-2">
                    <span className="text-ink-700 font-medium truncate">{l.name}</span>
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
                    {!detail && !l.type && <p className="text-ink-400">{l.description || '未知地点'}</p>}
                  </div>
                </details>
              );
            })}
            {j.locations.length === 0 && (
              <EmptyState icon="🗺️" title="还没有标记地点" hint="抵达或发现新地点后，这里会记录名称、状态、危险与关联角色。" />
            )}
          </div>
        )}

        {tab === 'notes' && (
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
        )}
      </div>
    </aside>
  );
}
