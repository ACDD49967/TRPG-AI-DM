/**
 * 游戏状态的共享类型。
 *
 * 从 gameStore 拆出：store 本体只留操作与持久化，类型单独成模块，
 * 供 store、SSE 钩子与状态面板复用（gameStore 仍再导出，兼容既有 import 路径）。
 */

/** 单次模型调用用量 */
export interface ModelCallMetric {
  phase: string;
  model: string;
  duration_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cache_hit_tokens?: number;
  success: boolean;
  streamed?: boolean;
  finish_reason?: string;
  error?: string;
}

/** 单回合耗时/调用/失败记录 */
export interface TurnMetrics {
  turn: number;
  duration_ms: number;
  phases_ms: Record<string, number>;
  model_calls: ModelCallMetric[];
  failures: string[];
}

/** 会话累计用量快照 */
export interface MetricsSnapshot {
  totals: {
    model_calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cache_hit_tokens: number;
    failures: number;
  };
  recent_turns: TurnMetrics[];
  active_turn?: TurnMetrics | null;
}

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
  inventory: Array<string | { name: string; description?: string; quantity?: number; type?: string; properties?: Record<string, unknown>; equipped?: boolean }>;
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
  skills?: Record<string, number>;
  saves?: Record<string, { value: number; proficient?: boolean }>;
  passive_perception?: number;
  feats?: Array<{ name: string; description?: string }>;
  /** 状态效果：中毒/麻痹/束缚等，由 update_state(conditions_add) 写入 */
  conditions?: Array<string | {
    name: string; description?: string; remaining_rounds?: number;
    damage_per_turn?: string | number; damage_type?: string; heal_per_turn?: number;
  }>;
  /** 正在专注的法术（5e）：受伤需掷体质豁免维持 */
  concentration?: { spell: string; level?: number } | null;
  /** 力竭等级（0-6，由 advance_time 的缺粮缺水与长休恢复共同维护） */
  exhaustion?: number;
  /** 伤害抗性/免疫/易伤（结构化字段，player_damage 管线读取） */
  damage_resistances?: string[];
  damage_immunities?: string[];
  damage_vulnerabilities?: string[];
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
  speed?: string;
  proficiency_bonus?: number;
  spell_slots?: number[] | { spell_slots?: number[]; pact_slots?: number; pact_slot_level?: number };
  class_resources?: Array<{ key: string; name: string; current: number; max: number; desc?: string }>;
  known_spells?: Array<{
    name: string; level: string; school?: string; description?: string;
    casting_time?: string; range?: string; components?: string; duration?: string;
    classes?: string[]; ritual?: boolean; prepared?: boolean;
  }>;
  action_points?: number;
  /** 4e 血竭（HP 降到上限一半以下）：后端在跨阈值时推送，角色卡显示标记 */
  bloodied?: boolean;
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
  /** 光照：明亮/微光/黑暗（后端 light_rules 归一，顶栏显示） */
  light?: string;
  /** 光源描述，如 火把 / 月光 / 无光 */
  light_source?: string;
}

/** 战斗日志条目 */
export interface CombatLogEntry {
  id: number;
  kind: 'combat' | 'enemy' | 'dice';
  text: string;
  extra?: Record<string, unknown>;
  time: string;
}

/** 先攻表条目（后端 backend/engine/initiative.py 推送，顺序与回合余额由后端维护） */
export interface InitiativeEntry {
  name: string;
  side: string;
  initiative: number;
  hp: number;
  max_hp: number;
  alive: boolean;
  turns_left: number;
  is_player: boolean;
  is_current: boolean;
}

/** 当前战斗轮的先攻顺序 */
export interface InitiativeState {
  round: number;
  current: string;
  order: InitiativeEntry[];
}

/** 战场态势条目：距离档位与掩体（后端 battlefield.py 推送） */
export interface BattlefieldPlacement {
  name: string;
  band: string;
  cover: string;
  note?: string;
}

/** 一条叙事行（文本 + 可选的骰子/事件标签） */
export interface NarrativeLine {
  id: number;
  text: string;
  role?: 'player' | 'dm';
  isDiceRoll?: boolean;
  diceData?: {
    skill: string;
    dc: number;
    roll: number;
    modifier: number;
    result: string;
    display?: string;
    advantage?: string;
    advantage_note?: string;
  };
  isGameEvent?: boolean;
  gameEventData?: {
    type: string;
    description: string;
    extra?: Record<string, unknown>;
  };
}
