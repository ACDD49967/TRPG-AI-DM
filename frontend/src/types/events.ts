/** SSE事件类型定义 —— 与后端 §3 协议对齐 */

/** 开场事件 */
export interface IntroEvent {
  scene: string;
  mood: string;
  seq?: number;
}

/** 打字机叙事token */
export interface NarrativeEvent {
  token: string;
  seq: number;
}

/** 跳过打字机直接显示完整段落 */
export interface NarrativeFlushEvent {
  full_text: string;
  seq?: number;
}

/** 骰子检定结果 */
export interface DiceRollEvent {
  skill: string;
  dc: number;
  roll: number;
  modifier: number;
  result: '成功' | '失败' | '大成功' | '大失败';
  seq?: number;
}

/** 角色状态更新（仅包含变化的字段） */
export interface StateUpdateEvent {
  hp?: number;
  max_hp?: number;
  mp?: number;
  max_mp?: number;
  xp?: number;
  gold?: number;
  inventory?: { items: string[] };
  level?: number;
  seq?: number;
  san?: number;
  maxSan?: number;
  luck?: number;
  healing_surges?: number;
  max_healing_surges?: number;
  surge_value?: number;
  game_system?: 'dnd5e' | 'dnd4e' | 'coc' | 'custom';
}

/** DM给出的建议选项 */
export interface ChoicesEvent {
  options: string[];
  seq?: number;
}

/** 游戏事件（战斗、遭遇等） */
export interface GameEvent {
  type: 'combat' | 'combat_start' | 'combat_end' | 'encounter' | 'quest_update';
  description: string;
  extra?: Record<string, unknown>;
  seq?: number;
}

/** 错误事件 */
export interface ErrorEvent {
  code: string;
  msg: string;
  seq?: number;
}

/** 场景更新 */
export interface SceneUpdateEvent {
  location: string;
  time: string;
  weather: string;
  atmosphere: string;
  npcs_here: string[];
  seq?: number;
}

/** 本轮结束 */
export interface EndOfTurnEvent {
  seq?: number;
}

/** 所有SSE事件的联合类型 */
export type SSECallback = {
  intro: (data: IntroEvent) => void;
  narrative: (data: NarrativeEvent) => void;
  narrative_flush: (data: NarrativeFlushEvent) => void;
  dice_roll: (data: DiceRollEvent) => void;
  state_update: (data: StateUpdateEvent) => void;
  choices: (data: ChoicesEvent) => void;
  game_event: (data: GameEvent) => void;
  error: (data: ErrorEvent) => void;
  end_of_turn: (data: EndOfTurnEvent) => void;
};
