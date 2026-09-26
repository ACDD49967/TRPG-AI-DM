/** 冒险笔记的数据层：SSE 快照、API 轮询兜底、地点图鉴合并与各页签计数。
 *
 * 从 `PlayerJournal.tsx` 拆出（那边只做布局与页签切换）。
 */
import { useEffect, useState } from 'react';
import { useGameStore } from '../../store/gameStore';
import type { JournalData } from './types';

export type JournalTab = 'npcs' | 'plot' | 'places' | 'notes' | 'memories';
export type MapsDetail = Array<{
  name: string;
  description?: string;
  details?: { type?: string; status?: string; culture?: string; districts?: string[]; notable_figures?: string; dangers?: string };
}>;

export function useJournalData() {
  const storeJournalData = useGameStore((s) => s.journalData);
  const { sessionId, isProcessing, status } = useGameStore();
  const journalStatus = useGameStore((s) => s.journalStatus);
  const [j, setJ] = useState<JournalData | null>(null);
  const [tab, setTab] = useState<JournalTab>('npcs');
  const [mapsDetail, setMapsDetail] = useState<MapsDetail>([]);

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

  // 界面内的世界状态修改（编辑面板、NPC 卡片）都会发这个事件；
  // 这里主动重拉一次笔记，不依赖 SSE 是否连着（此前事件只发没人听）。
  useEffect(() => {
    if (!sessionId) return;
    const reload = () => {
      fetch(`/api/game/${sessionId}/journal?username=${encodeURIComponent(status.username || 'default')}`)
        .then((r) => r.json())
        .then(setJ)
        .catch(() => {});
    };
    window.addEventListener('dnd:journal-refresh', reload);
    return () => window.removeEventListener('dnd:journal-refresh', reload);
  }, [sessionId, status.username]);

  if (!j || !j.npcs) {
    return { ready: false as const, j: null, tab, setTab, mapsDetail, journalStatus };
  }

  const npcs = j.npcs;
  const notableCount = j.notables?.length || 0;
  const notesCount =
    (j.character_notes?.quest_clues?.length || 0) + (j.character_notes?.npc_notes?.length || 0);
  // memories 由面板自己取数（见 journal/MemoriesPanel），这里不参与计数
  const tabCount: Partial<Record<JournalTab, number>> = {
    npcs: npcs.total + notableCount,
    plot: j.plot_flags.length + (j.world_events?.length || 0),
    places: j.locations.length,
    notes: notesCount,
  };
  return {
    ready: true as const, j, tab, setTab, mapsDetail, journalStatus,
    npcs, notableCount, notesCount, tabCount,
  };
}
