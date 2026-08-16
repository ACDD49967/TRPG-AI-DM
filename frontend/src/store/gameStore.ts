/** Zustand游戏状态管理 —— 全局状态与操作 */

import { create } from 'zustand';

/** 角色状态 */
export interface CharacterStatus {
  hp: number;
  maxHp: number;
  mp: number;
  maxMp: number;
  xp: number;
  gold: number;
  level: number;
  ac: number;
  inventory: string[];
  attributes: Record<string, number>;
  character_name?: string;
  race?: string;
  char_class?: string;
  gender?: string;
  game_system?: 'dnd5e' | 'dnd4e' | 'coc' | 'custom';
  username?: string;
  character_image?: string;
  scenario_id?: string;
  backstory?: string;
  skill_proficiencies?: string[];
  feats?: Array<{ name: string; description?: string }>;
  custom_classes?: string[];
  custom_skills?: string[];
  extra_attributes?: Record<string, string>;
  race_traits?: string[];
  class_proficiencies?: string[];
  hit_die?: string;
  san?: number;
  maxSan?: number;
  luck?: number;
  healing_surges?: number;
  max_healing_surges?: number;
  surge_value?: number;
  proficiency_bonus?: number;
  spell_slots?: number[] | { spell_slots?: number[]; pact_slots?: number };
  fortitude?: number;
  reflex?: number;
  will?: number;
  damage_bonus?: string;
  build?: number;
}

/** 场景信息（在顶栏显示） */
export interface SceneInfo {
  location: string;
  time: string;
  weather: string;
  npcs_here: string[];
}

/** 一条叙事行（文本 + 可选的骰子/事件标签） */
export interface NarrativeLine {
  id: number;
  text: string;
  isDiceRoll?: boolean;
  diceData?: {
    skill: string;
    dc: number;
    roll: number;
    modifier: number;
    result: string;
  };
  isGameEvent?: boolean;
  gameEventData?: {
    type: string;
    description: string;
    extra?: Record<string, unknown>;
  };
}

interface GameState {
  /** 当前会话ID */
  sessionId: string | null;
  /** 画面状态：start(入口) | playing(游戏中) */
  screen: 'start' | 'playing';

  /** 叙事行列表 */
  narrative: NarrativeLine[];
  /** 打字机当前累积的token */
  currentTokenBuffer: string;
  /** 叙事ID计数器 */
  narrativeId: number;

  /** 角色状态 */
  status: CharacterStatus;
  /** DM建议选项 */
  choices: string[];
  /** 是否正在等待AI回复（控制输入禁用） */
  isProcessing: boolean;
  /** 最新一次骰子结果（用于动画展示） */
  latestDiceRoll: {
    skill: string;
    dc: number;
    roll: number;
    modifier: number;
    result: string;
  } | null;
  /** 战斗中的敌人信息 */
  combat: {
    active: boolean;
    enemyName: string;
    enemyHp: number;
  } | null;

  /** 世界大纲 */
  worldOutline: string | null;
  /** DM决策建议（从AI回复中提取） */
  decisionSuggestions: string[];
  /** P2-12修复：Journal数据SSE推送——替代被动轮询 */
  journalData: Record<string, unknown> | null;
  /** 媒体内容版本号：AI 新增地图/生物后递增，触发前端重新拉取 */
  mediaVersion: number;
  /** 场景信息——在顶栏显示 */
  sceneInfo: SceneInfo;

  // ── 操作方法 ──

  /** 进入游戏 */
  setSession: (sessionId: string) => void;
  /** 追加一个打字机token */
  appendToken: (token: string) => void;
  /** 刷新当前缓冲区为一条叙事行 */
  flushBuffer: () => void;
  /** 强制设置叙事文本（用于narrative_flush和intro） */
  appendNarrativeText: (text: string) => void;
  /** 添加骰子结果行 */
  appendDiceRoll: (data: {
    skill: string;
    dc: number;
    roll: number;
    modifier: number;
    result: string;
  }) => void;
  /** 添加游戏事件行 */
  appendGameEvent: (data: {
    type: string;
    description: string;
    extra?: Record<string, unknown>;
  }) => void;
  /** 更新角色状态 */
  updateStatus: (update: Partial<CharacterStatus>) => void;
  /** 设置建议选项 */
  setChoices: (options: string[]) => void;
  /** 设置处理中状态 */
  setProcessing: (v: boolean) => void;
  /** 设置最新骰子结果 */
  setLatestDiceRoll: (data: GameState['latestDiceRoll']) => void;
  /** 更新战斗状态 */
  setCombat: (combat: GameState['combat']) => void;
  /** 设置世界大纲 */
  setWorldOutline: (outline: string) => void;
  /** 设置决策建议 */
  setDecisionSuggestions: (suggestions: string[]) => void;
  /** 从文本提取决策建议 */
  extractDecisions: (text: string) => void;
  /** P2-12修复：设置Journal数据（来自SSE推送） */
  setJournalData: (data: Record<string, unknown>) => void;
  /** 通知前端媒体（地图/图鉴）已更新 */
  bumpMediaVersion: () => void;
  /** 设置场景信息（来自SSE推送） */
  setSceneInfo: (data: Partial<SceneInfo>) => void;
  /** 重置游戏状态 */
  reset: () => void;
  /** 回到开始画面 */
  goToStart: () => void;
}

const initialStatus: CharacterStatus = {
  hp: 30,
  maxHp: 30,
  mp: 10,
  maxMp: 10,
  xp: 0,
  gold: 10,
  level: 1,
  ac: 10,
  inventory: [],
  attributes: { str: 12, dex: 12, con: 12, int: 12, wis: 12, cha: 12 },
  scenario_id: '',
};

const initialScene: SceneInfo = {
  location: '冒险的起点',
  time: '第1天',
  weather: '',
  npcs_here: [],
};

export const useGameStore = create<GameState>((set, get) => ({
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
  worldOutline: null,
  decisionSuggestions: [],
  journalData: null,
  mediaVersion: 0,
  sceneInfo: { ...initialScene },

  setSession: (sessionId) =>
    set({ sessionId, screen: 'playing', isProcessing: true }),

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

  /** 从AI回复文本中提取决策建议 */
  extractDecisions: (text: string) => {
    const lines = text.split('\n');
    const decisionIdx = lines.findIndex(l =>
      l.includes('决策建议') || l.includes('**决策建议**')
    );
    if (decisionIdx >= 0) {
      const suggestions = lines.slice(decisionIdx + 1)
        .filter(l => l.trim().startsWith('-') || l.trim().startsWith('*'))
        .map(l => l.replace(/^[-*]\s*/, '').replace(/\[|\]/g, '').trim())
        .filter(l => l.length > 0)
        .slice(0, 4);
      if (suggestions.length > 0) {
        get().setDecisionSuggestions(suggestions);
      }
    }
  },

  appendToken: (token) =>
    set((s) => ({ currentTokenBuffer: s.currentTokenBuffer + token })),

  flushBuffer: () => {
    const buf = get().currentTokenBuffer;
    if (!buf.trim()) return;
    const id = get().narrativeId;
    set((s) => ({
      narrative: [...s.narrative, { id, text: buf }],
      currentTokenBuffer: '',
      narrativeId: id + 1,
    }));
  },

  appendNarrativeText: (text) => {
    // 先刷新当前缓冲区
    const buf = get().currentTokenBuffer;
    if (buf.trim()) {
      get().flushBuffer();
    }
    // 追加新文本
    const id = get().narrativeId;
    set((s) => ({
      narrative: [...s.narrative, { id, text }],
      narrativeId: id + 1,
    }));
  },

  appendDiceRoll: (data) => {
    // 先刷新当前缓冲区
    const buf = get().currentTokenBuffer;
    if (buf.trim()) {
      get().flushBuffer();
    }
    const id = get().narrativeId;
    set((s) => ({
      narrative: [
        ...s.narrative,
        {
          id,
          text: `检定：${data.skill} d20=${data.roll}${data.modifier ? `+${data.modifier}` : ''} vs DC${data.dc} → ${data.result}`,
          isDiceRoll: true,
          diceData: data,
        },
      ],
      latestDiceRoll: data,
      narrativeId: id + 1,
      // 自动清理骰子弹窗（5秒后）
    }));
  },

  appendGameEvent: (data) => {
    const buf = get().currentTokenBuffer;
    if (buf.trim()) {
      get().flushBuffer();
    }
    const id = get().narrativeId;
    set((s) => ({
      narrative: [
        ...s.narrative,
        {
          id,
          text: `事件：${data.description}`,
          isGameEvent: true,
          gameEventData: data,
        },
      ],
      narrativeId: id + 1,
    }));
  },

  updateStatus: (update) =>
    set((s) => ({
      status: { ...s.status, ...update },
    })),

  setChoices: (options) => set({ choices: options }),

  setProcessing: (v) => set({ isProcessing: v }),

  setLatestDiceRoll: (data) => set({ latestDiceRoll: data }),

  setCombat: (combat) => set({ combat }),

  reset: () =>
    set({
      narrative: [],
      currentTokenBuffer: '',
      narrativeId: 0,
      status: { ...initialStatus },
      choices: [],
      isProcessing: false,
      latestDiceRoll: null,
      combat: null,
      worldOutline: null,
      decisionSuggestions: [],
      journalData: null,
      mediaVersion: 0,
      sceneInfo: { ...initialScene },
    }),

  goToStart: () =>
    set({
      screen: 'start',
      sessionId: null,
      narrative: [],
      currentTokenBuffer: '',
      narrativeId: 0,
      status: { ...initialStatus },
      choices: [],
      isProcessing: false,
      latestDiceRoll: null,
      combat: null,
      worldOutline: null,
      decisionSuggestions: [],
      journalData: null,
      mediaVersion: 0,
      sceneInfo: { ...initialScene },
    }),
}));
