/**
 * Zustand 游戏状态管理 —— 全局状态与操作。
 *
 * 类型在 gameTypes、契约与默认值在 gameStateShape；本文件只留 store 装配、
 * 操作实现与持久化配置。persist 的 key/version/migrate/partialize 契约保持不变，
 * localStorage 里已有的 dnd-game-state 可直接继续读取。
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CharacterStatus, SceneInfo } from './gameTypes';
import {
  freshSessionFields, initialScene, initialStatus, sanitizeStatusUpdate,
  type GameState,
} from './gameStateShape';
import { createNarrativeActions } from './actions/narrativeActions';

// 兼容既有导入路径：useSSE / DndCharacterSheet / MetricsCard 等仍可从本模块取类型
export type {
  BattlefieldPlacement, CharacterStatus, CombatLogEntry, InitiativeEntry, InitiativeState,
  MetricsSnapshot, ModelCallMetric, NarrativeLine, SceneInfo, TurnMetrics,
} from './gameTypes';
export type { GameState } from './gameStateShape';

export const useGameStore = create<GameState>()(persist((set, get) => ({
  sessionId: null,
  screen: 'start',
  narrative: [],
  currentTokenBuffer: '',
  narrativeId: 0,
  status: { ...initialStatus },
  choices: [],
  isProcessing: false,
  latestDiceRoll: null,
  combat: null,
  initiative: null,
  placements: [],
  combatLog: [],
  journalStatus: 'idle',
  worldOutline: null,
  decisionSuggestions: [],
  journalData: null,
  mediaVersion: 0,
  sceneInfo: { ...initialScene },
  metrics: null,
  pendingLevelUp: null,

  ...createNarrativeActions(set, get),

  setSession: (sessionId) =>
    set((s) => ({
      sessionId,
      screen: 'playing',
      isProcessing: true,
      // 切换剧本/存档时清空战斗面板与战斗记录，避免跨存档串场
      combat: s.sessionId === sessionId ? s.combat : null,
      combatLog: s.sessionId === sessionId ? s.combatLog : [],
    })),

  setWorldOutline: (outline: string) =>
    set({ worldOutline: outline }),

  setDecisionSuggestions: (suggestions: string[]) =>
    set({ decisionSuggestions: suggestions }),

  /** P2-12修复：SSE推送Journal数据 */
  setJournalData: (data: Record<string, unknown>) =>
    set({ journalData: data }),

  /** 通知前端媒体（地图/图鉴）已更新 */
  bumpMediaVersion: () =>
    set((s) => ({ mediaVersion: s.mediaVersion + 1 })),

  /** 设置场景信息 */
  setSceneInfo: (data: Partial<SceneInfo>) =>
    set((s) => ({ sceneInfo: { ...s.sceneInfo, ...data } })),

  updateStatus: (update) =>
    set((s) => ({ status: { ...s.status, ...sanitizeStatusUpdate(update) } })),

  setChoices: (options) => set({ choices: options }),

  setProcessing: (v) => set({ isProcessing: v }),

  setLatestDiceRoll: (data) => set({ latestDiceRoll: data }),

  setCombat: (combat) => set({ combat }),

  setInitiative: (initiative) => set({ initiative }),

  mergePlacements: (entries) =>
    set((s) => {
      const map = new Map(s.placements.map((p) => [p.name, p]));
      for (const entry of entries) {
        if (entry && entry.name) map.set(entry.name, { ...map.get(entry.name), ...entry });
      }
      return { placements: [...map.values()] };
    }),

  appendCombatLog: (entry) =>
    set((s) => ({
      combatLog: [
        ...s.combatLog,
        {
          ...entry,
          id: s.combatLog.length ? s.combatLog[s.combatLog.length - 1].id + 1 : 0,
          time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        },
      ].slice(-80),
    })),

  setJournalStatus: (status) => set({ journalStatus: status }),

  clearCombatLog: () => set({ combatLog: [] }),

  setMetrics: (metrics) => set({ metrics }),

  setPendingLevelUp: (level) => set({ pendingLevelUp: level }),

  reset: () =>
    set(freshSessionFields()),

  goToStart: () =>
    set({ ...freshSessionFields(), screen: 'start', sessionId: null }),
}), {
  name: 'dnd-game-state',
  version: 1,
  migrate: (persistedState: unknown, version: number) => {
    // P1-22: v0 -> v1 时截断历史，避免 localStorage 配额爆炸。
    if (!persistedState || typeof persistedState !== 'object') return persistedState as never;
    const p = persistedState as Record<string, unknown>;
    if (version < 1) {
      p.narrative = Array.isArray(p.narrative) ? (p.narrative as unknown[]).slice(-80) : [];
      p.combatLog = Array.isArray(p.combatLog) ? (p.combatLog as unknown[]).slice(-80) : [];
    }
    return p as never;
  },
  partialize: (state) => ({
    sessionId: state.sessionId,
    screen: state.screen,
    narrative: state.narrative.slice(-80),
    currentTokenBuffer: state.currentTokenBuffer,
    narrativeId: state.narrativeId,
    status: state.status,
    choices: state.choices,
    isProcessing: state.isProcessing,
    latestDiceRoll: state.latestDiceRoll,
    combat: state.combat,
    combatLog: state.combatLog.slice(-80),
    journalStatus: state.journalStatus,
    worldOutline: state.worldOutline,
    decisionSuggestions: state.decisionSuggestions,
    journalData: state.journalData,
    mediaVersion: state.mediaVersion,
    sceneInfo: state.sceneInfo,
  }),
}));
