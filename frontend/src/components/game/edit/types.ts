/**
 * 编辑面板共用的类型与常量。
 *
 * 从 EditPanel 拆出：六个标签页组件各自从这里取类型，
 * 避免把 world/character 的形状写回 any。
 */

export type Tab = 'scene' | 'npc' | 'location' | 'flag' | 'note' | 'items' | 'state' | 'settings';

export const TABS: Array<{ key: Tab; label: string; icon: string }> = [
  { key: 'scene', label: '场景', icon: '🗺️' },
  { key: 'npc', label: 'NPC', icon: '🧑' },
  { key: 'location', label: '地点', icon: '📍' },
  { key: 'flag', label: '旗标', icon: '🚩' },
  { key: 'note', label: '笔记', icon: '📝' },
  { key: 'items', label: '物品', icon: '🎒' },
  { key: 'state', label: '角色状态', icon: '❤️' },
  { key: 'settings', label: '会话设置', icon: '⚙️' },
];

export const ATTITUDES = ['敌对', '中立', '友好'];
export const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
export const ABILITY_CN: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
};

export interface NpcRow {
  name: string; role?: string; location?: string; attitude?: string;
  alive?: boolean; hp?: number; max_hp?: number; ac?: number; level?: number;
  personality?: string; motivation?: string; secret?: string; importance?: string;
}
export interface LocationRow { name: string; description?: string; status?: string; type?: string }
export interface FlagRow { key: string; status?: string; description?: string }
export interface NoteRow {
  target: string; target_type?: string; comment?: string; clue?: string;
  turn?: number; visible?: boolean;
}
export interface SceneRow {
  location: string; time: string; weather: string; atmosphere: string; day_count?: number;
  light?: string; light_source?: string;
}
export interface WorldState {
  scene: SceneRow; npcs: NpcRow[]; locations: LocationRow[]; plot_flags: FlagRow[];
  world_rules?: string | Record<string, unknown>; notes?: NoteRow[];
}
export interface CharacterState {
  character_info: Record<string, any>;
  conditions: Array<string | { name?: string; description?: string }>;
}
export interface SessionSettings {
  model_name?: string;
  base_url?: string;
  play_mode?: string;
  thinking_strength?: string;
}

/** 世界状态写回：与 DM 的 update_world_state 工具同一处理器。 */
export type SendWorld = (
  action: string, target: string, changes: Record<string, any>,
) => void;

/** 角色状态写回：与 DM 的 update_state 工具同一处理器。 */
export type SendState = (changes: Record<string, any>) => void;
