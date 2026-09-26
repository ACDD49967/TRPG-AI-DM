/**
 * 游戏状态的形状契约（字段 + action 签名）。
 *
 * 默认值/干净会话构造 → `initialSessionState`，SSE 字段白名单与清洗 → `statusWhitelist`；
 * 这里再导出，保持 `gameStore` / `narrativeActions` 的既有 import 路径不变。
 */
import type {
  BattlefieldPlacement, CharacterStatus, CombatLogEntry, InitiativeState,
  MetricsSnapshot, NarrativeLine, SceneInfo,
} from './gameTypes';

export interface GameState {
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
    /** 后端裁定的优势/劣势（advantage|disadvantage|normal）与来源说明 */
    advantage?: string;
    advantage_note?: string;
    /** 非 d20 规则（COC d100 等）的展示文本 */
    display?: string;
  } | null;
  /** 战斗中的敌人信息（enemies 支持多敌） */
  combat: {
    active: boolean;
    enemyName: string;
    enemyHp: number;
    enemies?: Array<{ name: string; hp: number; pending_regen?: boolean }>;
  } | null;
  /** 先攻顺序（战斗中由后端推送；后端是顺序与回合余额的唯一权威） */
  initiative: InitiativeState | null;
  /** 战场态势：各单位的距离档位与掩体（后端 battlefield.py） */
  placements: BattlefieldPlacement[];
  /** 战斗记录面板 */
  combatLog: CombatLogEntry[];
  /** 冒险笔记同步状态 */
  journalStatus: 'idle' | 'syncing' | 'synced';

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
  /** 会话累计的 token 用量与回合耗时统计 */
  metrics: MetricsSnapshot | null;
  /** 待分配的升级等级（属性提升/专长），null 表示无 */
  pendingLevelUp: number | null;

  // ── 操作方法 ──

  /** 进入游戏 */
  setSession: (sessionId: string) => void;
  /** 追加一个打字机token */
  appendToken: (token: string) => void;
  /** 刷新当前缓冲区为一条叙事行 */
  flushBuffer: () => void;
  /** 强制设置叙事文本（用于narrative_flush和intro） */
  appendNarrativeText: (text: string) => void;
  /** 添加玩家输入消息（用于对话轮次区分） */
  addPlayerMessage: (text: string) => void;
  /** 添加骰子结果行 */
  appendDiceRoll: (data: {
    skill: string;
    dc: number;
    roll: number;
    modifier: number;
    result: string;
    display?: string;
    advantage?: string;
    advantage_note?: string;
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
  /** 更新先攻顺序 */
  setInitiative: (initiative: InitiativeState | null) => void;
  /** 合并战场态势（同名覆盖） */
  mergePlacements: (entries: BattlefieldPlacement[]) => void;
  /** 追加战斗日志 */
  appendCombatLog: (entry: Omit<CombatLogEntry, 'id' | 'time'>) => void;
  /** 设置冒险笔记同步状态 */
  setJournalStatus: (status: GameState['journalStatus']) => void;
  /** 清空战斗日志 */
  clearCombatLog: () => void;
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
  /** 更新用量统计（回合结束后从后端拉取） */
  setMetrics: (metrics: MetricsSnapshot | null) => void;
  /** 设置待分配的升级等级 */
  setPendingLevelUp: (level: number | null) => void;
  /** 设置场景信息（来自SSE推送） */
  setSceneInfo: (data: Partial<SceneInfo>) => void;
  /** 重置游戏状态 */
  reset: () => void;
  /** 回到开始画面 */
  goToStart: () => void;
}

// 再导出：既有调用方（gameStore / narrativeActions / 浏览器脚本）import 路径不变
export { freshSessionFields, initialScene, initialStatus } from './initialSessionState';
export { sanitizeStatusUpdate } from './statusWhitelist';
